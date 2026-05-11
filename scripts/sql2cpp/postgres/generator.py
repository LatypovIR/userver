import os
import pathlib
import jinja2
from typing import Optional

from sql2cpp.utils import cpp_names
from sql2cpp.postgres import analyzer, models, migrations, translator

TEMPLATES_DIR = pathlib.Path(__file__).resolve().parent / 'templates'


def _jinja_env() -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    )


def _table_to_type(table: models.PgTable) -> models.PgType:
    return models.PgType(
        namespace=table.namespace,
        name=f'{table.name}_v{table.version}',
        fields=table.columns,
    )


def _table_like_type(table: models.PgTable, type_: models.PgType) -> bool:
    table_fields = sorted(table.columns, key=lambda v: v.name)
    type_fields = sorted(type_.fields, key=lambda v: v.name)

    if len(table_fields) != len(type_fields):
        return False

    for table_field, type_field in zip(table_fields, type_fields):
        if (table_field.name, table_field.type) != (type_field.name, type_field.type):
            return False

    return True


class PgGenerator:
    def __init__(
            self,
            namespace: str,
            output_dir: pathlib.Path,
            migrations_dir: pathlib.Path,
            queries_dir: Optional[pathlib.Path],
    ) -> None:
        self.namespace: str = namespace
        self.output_dir: pathlib.Path = output_dir
        self.migrations_dir: pathlib.Path = migrations_dir
        self.queries_dir: Optional[pathlib.Path] = queries_dir

        self.migrations: list[models.PgMigration] = migrations.load(self.migrations_dir)
        self.schemas: models.PgSchema = analyzer.PgSchemaAnalyzer().fetch_schema(self.migrations)

    def generate(self) -> None:
        os.makedirs(self.output_dir, exist_ok=True)
        PgMigrationGenerator(self).generate()
        PgCodeGenerator(self).generate()


class PgMigrationGenerator:
    def __init__(self, parent: PgGenerator):
        self.parent: PgGenerator = parent

    def generate(self) -> None:
        if not self.parent.migrations:
            return

        types_to_generate: list[models.PgType] = []

        for table in self.parent.schemas.tables.values():
            if table.type_name not in self.parent.schemas.types:
                types_to_generate.append(_table_to_type(table))
                continue

            if _table_like_type(table, self.parent.schemas.types[table.type_name]):
                continue

            print(f'WARNING: Conflict type {table.type_name} for table {table.pg_name}, skip it')

        if not types_to_generate:
            return

        version = self.parent.migrations[-1].next_version()
        template = _jinja_env().get_template('VX__codegen_migration.sql.j2')
        out_path = self.parent.migrations_dir / f'V{version}__codegen_migration.sql'
        out_path.write_text(template.render(
            types=types_to_generate,
        ))


class PgCodeGenerator:
    def __init__(self, base: PgGenerator):
        self.base = base
        self.types = base.schemas.types
        self.tables = base.schemas.tables
        self.enums = base.schemas.enums

    def pg_to_cpp_type(self, pg_type: models.PgColumn) -> translator.CppType:
        pg_typename = pg_type.type
        cpp_type = translator.pg_to_cpp_type(pg_typename)

        if not cpp_type and (pg_typename in self.enums or pg_typename in self.types):
            cpp_type = translator.CppType(
                typename=cpp_names.cpp_identifier_camel_case(pg_typename),
                includes=[],
            )

        if not cpp_type:
            raise ValueError(f'Unknown type: {pg_typename}')

        if pg_type.nullable:
            cpp_type.wrap_by_optional()

        return cpp_type

    def trust_typename(self, pg_typename: str) -> bool:
        if pg_typename not in self.types:
            return True

        pg_type = self.types[pg_typename]

        for table in self.tables.values():
            if table.type_name == pg_typename and _table_like_type(table, pg_type):
                return True

        return False

    def generate(self) -> None:
        user_types = [
            pg_type for pg_type in self.types.values() if not self.trust_typename(pg_type.pg_name)
        ]
        table_types = [
            _table_to_type(table) for table in self.tables.values() if self.trust_typename(table.type_name)
        ]

        structs_to_generate = [
            {
                'pg_name': type_.pg_name,
                'cpp_name': cpp_names.cpp_identifier_camel_case(type_.pg_name),
                'fields': [
                    {
                        'cpp_name': cpp_names.cpp_identifier_lower(field.name),
                        'cpp_type': self.pg_to_cpp_type(field).typename,
                    } for field in type_.fields
                ],
            }
            for type_ in sorted(user_types) + sorted(table_types)
        ]

        aliases_to_generate = [
            {
                'cpp_name_from': cpp_names.cpp_identifier_camel_case(table.pg_name),
                'cpp_name_to': cpp_names.cpp_identifier_camel_case(table.type_name),
            }
            for table in sorted(self.tables.values()) if self.trust_typename(table.type_name)
        ]

        enums_to_generate = [
            {
                'pg_name': enum.pg_name,
                'cpp_name': cpp_names.cpp_identifier_camel_case(enum.pg_name),
                'entries': [
                    {
                        'pg_name': value,
                        'cpp_name': cpp_names.cpp_enum_entry(value),
                    }
                    for value in enum.values
                ],
            }
            for enum in sorted(self.enums.values())
        ]

        includes_to_generate: list[str] = []

        for type_ in user_types + table_types:
            for field in type_.fields:
                includes_to_generate += self.pg_to_cpp_type(field).includes

        if structs_to_generate:
            includes_to_generate.append('<userver/storages/postgres/io/io_fwd.hpp>')

        if enums_to_generate:
            includes_to_generate.append('<userver/storages/postgres/io/enum_types.hpp>')

        template = _jinja_env().get_template('models.hpp.j2')
        out_path = self.base.output_dir / 'models.hpp'
        out_path.write_text(template.render(
            namespace=self.base.namespace,
            includes=list(sorted(set(includes_to_generate))),
            structs=structs_to_generate,
            enums=enums_to_generate,
            aliases=aliases_to_generate,
        ))
