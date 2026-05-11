from __future__ import annotations
import pathlib
from dataclasses import dataclass, field


@dataclass(order=True)
class PgColumn:
    name: str
    type: str
    nullable: bool


@dataclass(order=True)
class PgTable:
    namespace: str
    name: str
    columns: list[PgColumn]
    version: int = field(compare=False)

    @property
    def pg_name(self) -> str:
        return f'{self.namespace}.{self.name}'

    @property
    def type_name(self) -> str:
        return f'{self.pg_name}_v{self.version}'


@dataclass(order=True)
class PgType:
    namespace: str
    name: str
    fields: list[PgColumn]

    @property
    def pg_name(self) -> str:
        return f'{self.namespace}.{self.name}'


@dataclass(order=True)
class PgEnum:
    namespace: str
    name: str
    values: list[str]

    @property
    def pg_name(self) -> str:
        return f'{self.namespace}.{self.name}'


@dataclass
class PgSchema:
    tables: dict[str, PgTable]
    types: dict[str, PgType]
    enums: dict[str, PgEnum]


@dataclass(order=True)
class PgMigration:
    path: pathlib.Path
    version: str
    sql: str

    def next_version(self) -> str:
        digits: int = len(self.version)
        version: int = int(self.version)
        return f'{version + 1:0{digits}d}'
