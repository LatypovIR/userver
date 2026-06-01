from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


@dataclass(order=True)
class Migration:
    path: pathlib.Path
    version: str
    sql: str

    def next_version(self) -> str:
        digits: int = len(self.version)
        version: int = int(self.version)
        return f"{version + 1:0{digits}d}"


class QueryCardinality(str, Enum):
    one = "one"
    many = "many"
    optional = "optional"


@dataclass(order=True)
class QueryParam:
    type: Optional[str]
    nullable: Optional[bool]


@dataclass(order=True)
class Query:
    path: pathlib.Path
    sql: str
    no_codegen: bool
    args: list[QueryParam]
    returns: list[QueryParam]
    cardinality: Optional[QueryCardinality]


@dataclass(order=True)
class QuerySchema:
    name: str
    sql: str
    args: list[QueryParam]
    returns: list[QueryParam]
    cardinality: QueryCardinality


@dataclass(order=True)
class Column:
    name: str
    type: str
    nullable: bool


@dataclass(order=True)
class Table:
    namespace: str
    name: str
    columns: list[Column]
    version: int = field(compare=False)

    @property
    def db_name(self) -> str:
        return f"{self.namespace}.{self.name}"

    @property
    def type_name(self) -> str:
        return f"{self.db_name}_v{self.version}"


@dataclass(order=True)
class StructType:
    namespace: str
    name: str
    fields: list[Column]

    @property
    def db_name(self) -> str:
        return f"{self.namespace}.{self.name}"


@dataclass(order=True)
class DbEnum:
    namespace: str
    name: str
    values: list[str]

    @property
    def db_name(self) -> str:
        return f"{self.namespace}.{self.name}"


@dataclass
class Catalog:
    tables: dict[str, Table]
    types: dict[str, StructType]
    enums: dict[str, DbEnum]

    def sorted_enums(self) -> list[DbEnum]:
        return sorted(self.enums.values(), key=lambda x: x.db_name)

    def sorted_tables(self) -> list[Table]:
        return sorted(self.tables.values(), key=lambda x: x.db_name)

    def sorted_types(self) -> list[StructType]:
        result = []
        remaining = sorted(self.types.values(), key=lambda x: x.db_name)

        while remaining:
            for remain in remaining:
                depends = {
                    field.type
                    for field in remain.fields
                    if field.type in self.types
                }
                if depends.issubset({type_.db_name for type_ in result}):
                    result.append(remain)
                    remaining.remove(remain)
                    break

        return result


@dataclass(order=True)
class Schema:
    catalog: Catalog
    queries: list[QuerySchema]
