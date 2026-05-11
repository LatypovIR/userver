from __future__ import annotations

from sql2cpp.postgres import models, runner


class PgSchemaAnalyzer:
    def __init__(self):
        self.schema: models.PgSchema = models.PgSchema(tables={}, types={}, enums={})

    def get_schema(self) -> models.PgSchema:
        return self.schema

    def fetch_schema(self, migrations: list[models.PgMigration]) -> models.PgSchema:
        with runner.PgRunner() as pg, pg.connect() as conn, conn.cursor() as cursor:
            for migration in migrations:
                cursor.execute(migration.sql)
                self.update_schema(cursor)

        return self.get_schema()

    def update_schema(self, cursor) -> None:
        for new_table in self.read_tables(cursor=cursor).values():
            old_table = self.schema.tables.get(new_table.pg_name)

            if not old_table:
                new_table.version = 0

            elif old_table != new_table:
                new_table.version = old_table.version + 1

            else:
                new_table.version = old_table.version

            self.schema.tables[new_table.pg_name] = new_table

        self.schema.types = self.read_types(cursor=cursor)
        self.schema.enums = self.read_enums(cursor=cursor)

    @staticmethod
    def read_tables(cursor) -> dict[str, models.PgTable]:
        sql = '''
            SELECT
                nspname AS namespace_name,
                relname AS table_name,
                attname AS column_name,
                format_type(atttypid, atttypmod) AS column_type,
                attnotnull AS column_not_nullable
            FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE a.attnum > 0 AND
            NOT a.attisdropped AND
            n.nspname NOT IN ('pg_catalog', 'information_schema') AND
            (
                c.relkind = 'p' OR
                (c.relkind = 'r' AND NOT c.relispartition) OR
                c.relkind IN ('v', 'm')
            )
            ORDER BY n.nspname, c.relname, a.attnum
        '''

        cursor.execute(sql)
        rows = cursor.fetchall()

        tables: dict[str, models.PgTable] = {}
        for row in rows:
            namespace_name = row[0]
            table_name = row[1]
            column_name = row[2]
            column_type = row[3]
            column_nullable = not row[4]

            column = models.PgColumn(
                name=column_name,
                type=column_type,
                nullable=column_nullable,
            )

            table = models.PgTable(
                namespace=namespace_name,
                name=table_name,
                columns=[column],
                version=0,
            )

            if table.pg_name in tables:
                tables[table.pg_name].columns.append(column)
            else:
                tables[table.pg_name] = table

        return tables

    @staticmethod
    def read_types(cursor) -> dict[str, models.PgType]:
        sql = '''
            SELECT
                n.nspname AS namespace_name,
                t.typname AS type_name,
                a.attname AS field_name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) AS field_type
            FROM pg_catalog.pg_type t
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            JOIN pg_catalog.pg_class c ON c.oid = t.typrelid
            JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
            WHERE t.typtype = 'c'
            AND c.relkind = 'c'
            AND a.attnum > 0
            AND NOT a.attisdropped
            AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY n.nspname, c.relname, a.attnum
        '''

        cursor.execute(sql)
        rows = cursor.fetchall()

        types: dict[str, models.PgType] = {}
        for row in rows:
            namespace_name = row[0]
            type_name = row[1]
            field_name = row[2]
            field_type = row[3]

            field = models.PgColumn(
                name=field_name,
                type=field_type,
                nullable=True,  # all fields are nullable
            )

            type_ = models.PgType(
                namespace=namespace_name,
                name=type_name,
                fields=[field],
            )

            if type_.pg_name in types:
                types[type_.pg_name].fields.append(field)
            else:
                types[type_.pg_name] = type_

        return types

    @staticmethod
    def read_enums(cursor) -> dict[str, models.PgEnum]:
        sql = '''
        SELECT
            n.nspname AS namespace_name,
            t.typname AS type_name,
            e.enumlabel AS enum_value
        FROM pg_catalog.pg_enum e
        JOIN pg_catalog.pg_type t ON t.oid = e.enumtypid
        JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY n.nspname, t.typname, e.enumsortorder
        '''

        cursor.execute(sql)
        rows = cursor.fetchall()

        enums: dict[str, models.PgEnum] = {}
        for row in rows:
            namespace_name = row[0]
            type_name = row[1]
            enum_value = row[2]

            enum = models.PgEnum(
                namespace=namespace_name,
                name=type_name,
                values=[enum_value],
            )

            if enum.pg_name in enums:
                enums[enum.pg_name].values.append(enum_value)
            else:
                enums[enum.pg_name] = enum

        return enums
