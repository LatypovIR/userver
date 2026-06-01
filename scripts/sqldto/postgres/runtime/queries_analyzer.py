from __future__ import annotations

import copy
import uuid

from sqldto.postgres import samples
from sqldto.sql import models
from sqldto.utils import log

logger = log.logger


class PgQueryAnalyzer:
    def __init__(self, catalog: models.Catalog):
        self.catalog: models.Catalog = catalog

    def read_schemas(
        self,
        cursor,
        queries: list[models.Query],
    ) -> list[models.QuerySchema]:
        return [self.read_schema(cursor, query) for query in queries if not query.no_codegen]

    def read_schema(
        self,
        cursor,
        query: models.Query,
    ) -> models.QuerySchema:
        PG_DEFAULT_TYPE = "text"
        PG_ALTERNATIVE_TYPE = "integer"

        try:
            params, returns = self.read_params(cursor, query, [])
        except Exception as ex:
            # example: UNNEST($1), $1.field
            logger.warning(
                "[%s] Impossible to determine params: %s",
                query.path.stem,
                ex,
            )
            raise Exception(f"Can't analyze query {query.path.name}")

        for i in range(len(params)):
            if params[i].type != PG_DEFAULT_TYPE:
                continue

            if len(query.args) > i and query.args[i].type:
                continue

            params[i].type = PG_ALTERNATIVE_TYPE
            try:
                self.read_params(cursor, query, params)
                params[i].type = None  # example: SELECT $1
            except Exception:
                params[i].type = PG_DEFAULT_TYPE  # explicitly cast

            if not params[i].type:
                logger.warning(
                    "[%s] Implicitly casts param $%s as text",
                    query.path.stem,
                    i,
                )
                raise Exception(f"Can't analyze query {query.path.name}")

        for i in range(len(params)):
            if params[i].nullable is not None:
                continue

            params[i].nullable = True
            try:
                self.read_params(cursor, query, params)
            except Exception:
                params[i].nullable = False  # pg require not null arg

        return models.QuerySchema(
            name=query.path.stem,
            sql=query.sql,
            args=params,
            returns=returns,
            cardinality=query.cardinality or models.QueryCardinality.many,
        )

    def guess_return_type(self, pg_typename: str, cursor, column) -> models.QueryParam:
        if column.table_oid is not None and column.table_column is not None:
            # TODO: conflicts with public namespace
            cursor.execute(f"""
                SELECT pg_catalog.format_type(a.atttypid, a.atttypmod)
                FROM pg_catalog.pg_attribute a
                JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
                JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
                WHERE a.attrelid = {column.table_oid}
                AND a.attnum = {column.table_column}
                AND NOT a.attisdropped
            """)

            return models.QueryParam(
                type=cursor.fetchall()[0][0],
                nullable=True,  # TODO: How to determine nullable?
            )

        if pg_typename == "numeric" and column.precision is not None and column.scale is not None:
            return models.QueryParam(
                type=f"{pg_typename}({column.precision},{column.scale})",
                nullable=True,
            )

        return models.QueryParam(
            type=pg_typename,
            nullable=True,
        )

    def read_params(
        self,
        cursor,
        query: models.Query,
        params: list[models.QueryParam],
    ) -> (
        list[models.QueryParam],
        list[models.QueryParam],
    ):
        stmt = f"_{uuid.uuid4().hex}"
        args = copy.deepcopy(params) if params else copy.deepcopy(query.args)
        types = [arg.type or "unknown" for arg in args]
        types_hint = f"({', '.join(types)})" if types else ""

        cursor.execute(f"PREPARE {stmt} {types_hint} AS {query.sql}")
        cursor.execute(f"""
            SELECT
                pg_catalog.format_type(p.type_oid, NULL) AS type_name
            FROM pg_catalog.pg_prepared_statements ps
            CROSS JOIN LATERAL unnest(ps.parameter_types::oid[])
                WITH ORDINALITY AS p(type_oid, ord)
            WHERE ps.name = '{stmt}'
            ORDER BY p.ord;
        """)

        for i, row in enumerate(cursor.fetchall()):
            type = row[0]
            nullable = None

            if len(args) > i and args[i].type:
                type = args[i].type

            if len(args) > i and args[i].nullable is not None:
                nullable = args[i].nullable

            if i == len(args):
                args.append(None)

            args[i] = models.QueryParam(
                type=type,
                nullable=nullable,
            )

        cursor.execute("BEGIN")
        
        try:
            values = [samples.sample(arg, self.catalog) for arg in args]
            values_hint = f"({', '.join(values)})" if values else ""

            # TODO: disable all constraints: foreign keys, checks, etc...
            cursor.execute(f"EXECUTE {stmt}{values_hint}")
            description = cursor.description or []

            cursor.execute(
                "SELECT pg_catalog.format_type(oid, NULL) FROM unnest(%s::oid[]) AS oid",
                ([column.type_code for column in description],),
            )
            return_types = cursor.fetchall()
            returns = [
                self.guess_return_type(return_type[0], cursor, column)
                for return_type, column in zip(return_types, description)
            ]
        except Exception as ex:
            raise ex
        finally:
            cursor.execute("ROLLBACK")
            cursor.execute(f"DEALLOCATE {stmt}")
        return args, returns

