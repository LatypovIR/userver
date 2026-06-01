import pathlib
import re

from sqldto.sql import models
from sqldto.utils import log

MIGRATION_PATTERN = re.compile(r"^V(\d+)__.+\.sql$")

logger = log.logger


def load(migrations_dir: pathlib.Path) -> list[models.Migration]:
    if not migrations_dir.is_dir():
        raise ValueError(f"Not a directory: {migrations_dir}")

    logger.debug("Loading migrations from %s", migrations_dir)

    paths = sorted(migrations_dir.glob("*.sql"), key=lambda p: p.name)
    migrations = [
        models.Migration(
            path=path,
            version=matched.group(1),
            sql=path.read_text(),
        )
        for path in paths
        if (matched := MIGRATION_PATTERN.match(path.name))
    ]

    return sorted(migrations, key=lambda v: int(v.version))
