from __future__ import annotations

from sqldto.postgres import runner
from sqldto.postgres.runtime import catalog_analyzer, queries_analyzer
from sqldto.sql import models


class PgSchemaAnalyzer:
    def __init__(
        self, migrations: list[models.Migration], queries: list[models.Query]
    ):
        self.migrations: list[models.Migration] = migrations
        self.queries: list[models.Query] = queries

    def fetch(self) -> models.Schema:
        pg_catalog_analyzer = catalog_analyzer.PgCatalogAnalyzer()

        with runner.PgRunner() as pg, pg.connect() as conn, conn.cursor() as cursor:
            pg_catalog_analyzer.apply_migrations(cursor, self.migrations)
            catalog = pg_catalog_analyzer.catalog
            
            conn.commit()

            pg_query_analyzer = queries_analyzer.PgQueryAnalyzer(catalog)
            queries = pg_query_analyzer.read_schemas(cursor, self.queries)

            return models.Schema(catalog=catalog, queries=queries)
