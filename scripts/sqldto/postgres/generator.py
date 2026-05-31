from __future__ import annotations

import pathlib
from typing import Optional

from sqldto.postgres import analyzer, translator
from sqldto.sql import migrations, models, queries
from sqldto.utils import cpp_names, log, render

logger = log.logger

TEMPLATES_DIR = pathlib.Path(__file__).resolve().parent / "templates"


def _table_to_type(table: models.Table) -> models.StructType:
    return models.StructType(
        namespace=table.namespace,
        name=f"{table.name}_v{table.version}",
        fields=table.columns,
    )


def _table_like_type(table: models.Table, type_: models.StructType) -> bool:
    table_fields = sorted(table.columns, key=lambda v: v.name)
    type_fields = sorted(type_.fields, key=lambda v: v.name)

    if len(table_fields) != len(type_fields):
        return False

    for table_field, type_field in zip(table_fields, type_fields):
        if (table_field.name, table_field.type) != (type_field.name, type_field.type):
            return False

    return True


class PgGenerator(render.GeneratorBase):
    def __init__(
        self,
        namespace: str,
        output_headers_dir: pathlib.Path,
        output_sources_dir: pathlib.Path,
        clang_format: Optional[str],
        migrations_dir: pathlib.Path,
        queries_dir: Optional[pathlib.Path],
    ) -> None:
        super().__init__(TEMPLATES_DIR, clang_format=clang_format)
        self.namespace: str = namespace
        self.output_headers_dir: pathlib.Path = output_headers_dir
        self.output_sources_dir: pathlib.Path = output_sources_dir
        self.migrations_dir: pathlib.Path = migrations_dir
        self.queries_dir: Optional[pathlib.Path] = queries_dir

        self.migrations = migrations.load(self.migrations_dir)
        self.queries = (
            queries.load(self.queries_dir) if self.queries_dir else []
        )
        self.schemas: models.Schema = analyzer.PgSchemaAnalyzer(
            self.migrations, self.queries
        ).fetch()

    def generate(self) -> None:
        migration = PgMigrationGenerator(self).generate()
        pg_models = PgModelsGenerator(self).generate()
        pg_queries = PgQueriesGenerator(self).generate()

        for to_generate in [migration, pg_models, *pg_queries]:
            if to_generate:
                super().render(to_generate)


class PgMigrationGenerator:
    def __init__(self, parent: PgGenerator):
        self.parent: PgGenerator = parent

    def generate(self) -> Optional[render.ToGenerate]:
        if not self.parent.migrations:
            return None

        types_to_generate: list[models.StructType] = []

        for table in self.parent.schemas.catalog.tables.values():
            if table.type_name not in self.parent.schemas.catalog.types:
                types_to_generate.append(_table_to_type(table))
                continue

            if _table_like_type(
                table, self.parent.schemas.catalog.types[table.type_name]
            ):
                continue

            logger.warning(
                "Conflict type %s for table %s, skip it",
                table.type_name,
                table.db_name,
            )

        if not types_to_generate:
            return None

        version = self.parent.migrations[-1].next_version()

        return render.ToGenerate(
            template_name="VX__codegen_migration.sql.j2",
            output_file=self.parent.migrations_dir
            / f"V{version}__codegen_migration.sql",
            context={
                "types": types_to_generate,
            },
        )


class PgModelsGenerator:
    def __init__(self, base: PgGenerator):
        self.base = base
        self.catalog = base.schemas.catalog

    def pg_to_cpp_type(
        self,
        pg_object: models.Column | models.StructType | models.DbEnum,
        includes_accumulator: set[str] = set(),
    ) -> translator.CppType:
        pg_typename: str = None
        nullable: bool = None

        if isinstance(pg_object, models.Column):
            pg_typename = pg_object.type
            nullable = pg_object.nullable

        elif isinstance(pg_object, models.StructType):
            pg_typename = pg_object.db_name
            nullable = False

        elif isinstance(pg_object, models.DbEnum):
            pg_typename = pg_object.db_name
            nullable = False

        cpp_type = translator.pg_to_cpp_type(
            pg_typename,
            nullable,
            self.catalog,
        )

        if not cpp_type:
            raise ValueError(f"Unknown type: {pg_typename}")

        for template in cpp_type.templates:
            if not template.value:
                raise ValueError(
                    f"Unsupported type: {pg_typename} that requires templates"
                )

        includes_accumulator.update(cpp_type.includes)
        return cpp_type

    def trust_typename(self, pg_typename: str) -> bool:
        if pg_typename not in self.catalog.types:
            return True

        pg_type = self.catalog.types[pg_typename]

        for table in self.catalog.tables.values():
            if table.type_name == pg_typename and _table_like_type(table, pg_type):
                return True

        return False

    def generate(self) -> Optional[render.ToGenerate]:
        includes_to_generate: set[str] = set()
        user_types = [
            pg_type
            for pg_type in self.catalog.sorted_types()
            if not self.trust_typename(pg_type.db_name)
        ]
        table_types = [
            _table_to_type(table)
            for table in self.catalog.sorted_tables()
            if self.trust_typename(table.type_name)
        ]

        enums_to_generate = [
            {
                "db_name": enum.db_name,
                "cpp_type": self.pg_to_cpp_type(enum, includes_to_generate),
                "entries": [
                    {
                        "name": value,
                        "cpp_name": cpp_names.cpp_enum_entry(value),
                    }
                    for value in enum.values
                ],
            }
            for enum in self.catalog.sorted_enums()
        ]

        structs_to_generate = [
            {
                "db_name": type_.db_name,
                "cpp_type": self.pg_to_cpp_type(type_, includes_to_generate),
                "fields": [
                    {
                        "cpp_name": cpp_names.cpp_identifier_lower(field.name),
                        "cpp_type": self.pg_to_cpp_type(field, includes_to_generate),
                    }
                    for field in type_.fields
                ],
            }
            for type_ in user_types + table_types
        ]

        aliases_to_generate = [
            {
                "cpp_name_from": translator.pg_name_to_cpp_name(table.db_name),
                "cpp_name_to": self.pg_to_cpp_type(_table_to_type(table)).typename,
            }
            for table in self.catalog.sorted_tables()
            if self.trust_typename(table.type_name)
        ]

        return render.ToGenerate(
            template_name="pg_models.hpp.j2",
            output_file=self.base.output_headers_dir / "pg_models.hpp",
            context={
                "namespace": self.base.namespace,
                "includes": list(sorted(set(includes_to_generate))),
                "structs": structs_to_generate,
                "enums": enums_to_generate,
                "aliases": aliases_to_generate,
            },
            clang_format=True,
        )


class PgQueriesGenerator:
    def __init__(self, base: PgGenerator):
        self.base = base
        self.catalog = base.schemas.catalog

    def pg_to_cpp_type(
        self,
        param: models.QueryParam,
        includes_accumulator: set[str] = set(),
    ) -> list[translator.CppType]:
        cpp_type = translator.pg_to_cpp_type(
            param.type, param.nullable, self.catalog)

        if not cpp_type:
            raise ValueError(f"Unknown type: {param.type}")

        for template in cpp_type.templates:
            if not template.value:
                raise ValueError(
                    f"Unsupported type: {param.type} that requires templates"
                )

        includes_accumulator.update(cpp_type.includes)
        return cpp_type

    def generate(self) -> Optional[render.ToGenerate]:
        includes_to_generate: set[str] = {
            "<userver/storages/postgres/cluster.hpp>",
            "<userver/storages/postgres/postgres_fwd.hpp>",
        }

        queries_to_generate: list[dict] = []
        for query in self.base.schemas.queries:
            args = [
                {
                    "cpp_type": self.pg_to_cpp_type(param, includes_to_generate),
                }
                for param in query.args
            ]

            returns = [
                {
                    "cpp_type": self.pg_to_cpp_type(param, includes_to_generate),
                }
                for param in query.returns
            ]

            if len(returns) > 1:
                includes_to_generate.add(
                    "<userver/storages/postgres/io/row_types.hpp>",
                )

            queries_to_generate.append({
                "name": query.name,
                "cpp_name": cpp_names.cpp_identifier_camel_case(query.name),
                "sql": query.sql.strip(),
                "args": args,
                "returns": returns,
                "cardinality": query.cardinality,
            })

        context = {
            "namespace": self.base.namespace,
            "includes": list(sorted(set(includes_to_generate))),
            "queries": queries_to_generate,
        }

        return [
            render.ToGenerate(
                template_name="pg_client.hpp.j2",
                output_file=self.base.output_headers_dir / "pg_client.hpp",
                context=context,
                clang_format=True,
            ),
            render.ToGenerate(
                template_name="pg_cluster.hpp.j2",
                output_file=self.base.output_headers_dir / "pg_cluster.hpp",
                context=context,
                clang_format=True,
            ),
            render.ToGenerate(
                template_name="pg_mock.hpp.j2",
                output_file=self.base.output_headers_dir / "pg_mock.hpp",
                context=context,
                clang_format=True,
            ),
            render.ToGenerate(
                template_name="pg_cluster.cpp.j2",
                output_file=self.base.output_sources_dir / "pg_cluster.cpp",
                context=context,
                clang_format=True,
            ),
        ]
