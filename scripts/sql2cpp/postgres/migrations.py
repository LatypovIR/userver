import re
import pathlib

from sql2cpp.postgres import models

MIGRATION_PATTERN = re.compile(r'^V(\d+)__.+\.sql$')


def load(migrations_dir: pathlib.Path) -> list[models.PgMigration]:
    if not migrations_dir.is_dir():
        raise ValueError(f'Not a directory: {migrations_dir}')
    
    print(f'Loading migrations from {migrations_dir}')

    paths = sorted(migrations_dir.glob('*.sql'), key=lambda p: p.name)
    migrations = [
        models.PgMigration(
            path=path,
            version=matched.group(1),
            sql=path.read_text(),
        )
        for path in paths
        if (matched := MIGRATION_PATTERN.match(path.name))
    ]

    return sorted(migrations, key=lambda v: int(v.version))
