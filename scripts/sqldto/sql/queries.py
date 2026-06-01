import pathlib
import re
import sqlparse
from typing import Optional

from sqldto.sql import models
from sqldto.utils import log

QUERY_PATTERN = re.compile(r"^.+\.sql$")

logger = log.logger


def parse_comments(sql: str) -> list[str]:
    parsed = sqlparse.parse(sql)
    comments = []
    for stmt in parsed:
        for token in stmt.flatten():
            if token.ttype in sqlparse.tokens.Comment:
                comments.append(str(token).strip())
    return comments


def parse_no_codegen(comments: list[str]) -> bool:
    for comment in comments:
        for token in comment.split(" "):
            if token == "@no-codegen":
                return True
    return False


def parse_cardinality(comments: list[str]) -> Optional[models.QueryCardinality]:
    for comment in comments:
        for token in comment.split(" "):
            if token == "@one":
                return models.QueryCardinality.one
            if token == "@many":
                return models.QueryCardinality.many
            if token == "@optional":
                return models.QueryCardinality.optional
    return None


def parse_args(comments: list[str]) -> list[models.QueryParam]:
    ARG_PATTERN = re.compile(r"@arg(\d+):\s*(.+?)(?=\s+@arg\d+:|$)")

    overrides: dict[int, str] = {}
    for comment in comments:
        for m in ARG_PATTERN.finditer(comment):
            overrides[int(m.group(1))] = m.group(2).strip()

    max_index = max([0] + list(overrides.keys()))
    return [
        models.QueryParam(
            type=overrides.get(i + 1),
            nullable=None,
        )
        for i in range(max_index)
    ]


def parse_returns(comments: list[str]) -> list[models.QueryParam]:
    # TODO: parse client returns overrides
    return []


def load(queries_dir: pathlib.Path) -> list[models.Query]:
    if not queries_dir.is_dir():
        raise ValueError(f"Not a directory: {queries_dir}")

    logger.debug("Loading queries from %s", queries_dir)

    def parse(path: pathlib.Path) -> models.Query:
        sql = path.read_text()
        comments = parse_comments(sql)

        return models.Query(
            path=path,
            sql=sql,
            no_codegen=parse_no_codegen(comments),
            args=parse_args(comments),
            returns=parse_returns(comments),
            cardinality=parse_cardinality(comments),
        )

    paths = sorted(queries_dir.rglob("*.sql"), key=lambda p: p.name)
    queries = [parse(path) for path in paths]
    return sorted(queries, key=lambda q: q.path.name)
