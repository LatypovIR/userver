import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class CppType:
    typename: str
    includes: list[str]

    def wrap_by_optional(self) -> None:
        self.typename = f'std::optional<{self.typename}>'
        self.includes.append('<userver/storages/postgres/io/optional.hpp>')


def pg_to_cpp_type(pg_type: str) -> Optional[CppType]:
    if cpp_type := pg_to_floating_cpp_type(pg_type):
        return cpp_type

    if cpp_type := pg_to_integral_cpp_type(pg_type):
        return cpp_type

    if cpp_type := pg_to_str_cpp_type(pg_type):
        return cpp_type

    if cpp_type := pg_to_decimal_cpp_type(pg_type):
        return cpp_type

    if cpp_type := pg_to_chrono_cpp_type(pg_type):
        return cpp_type

    if cpp_type := pg_to_json_cpp_type(pg_type):
        return cpp_type

    return None


def pg_to_floating_cpp_type(pg_type: str) -> Optional[CppType]:
    mapping = {
        'real': 'float',
        'double precision': 'double',
    }

    if pg_type in mapping:
        return CppType(
            typename=mapping[pg_type],
            includes=['<userver/storages/postgres/io/floating_point_types.hpp>'],
        )

    return None


def pg_to_integral_cpp_type(pg_type: str) -> Optional[CppType]:
    mapping = {
        'boolean': 'bool',
        'smallint': 'std::int16_t',
        'integer': 'std::int32_t',
        'bigint': 'std::int64_t',
        'smallserial': 'std::int16_t',
        'serial': 'std::int32_t',
        'bigserial': 'std::int64_t',
    }

    if pg_type in mapping:
        return CppType(
            typename=mapping[pg_type],
            includes=['<userver/storages/postgres/io/integral_types.hpp>'],
        )

    return None


def pg_to_str_cpp_type(pg_type: str) -> Optional[CppType]:
    mapping = {
        re.compile(r'^char$'): r'char',
        re.compile(r'^text$'): r'std::string',
        re.compile(r'^character(\((\d+)\))?$'): r'std::string',
        re.compile(r'^character varying(\((\d+)\))?$'): r'std::string',
    }

    for pattern, cpp_type in mapping.items():
        matched = pattern.fullmatch(pg_type)
        if matched:
            return CppType(
                typename=matched.expand(cpp_type),
                includes=['<userver/storages/postgres/io/string_types.hpp>'],
            )

    return None


def pg_to_decimal_cpp_type(pg_type: str) -> Optional[CppType]:
    mapping = {
        re.compile(r'^numeric\((\d+),(\d+)\)$'): r'decimal64::Decimal<\2>',
        re.compile(r'^decimal\((\d+),(\d+)\)$'): r'decimal64::Decimal<\2>',
    }

    for pattern, cpp_type in mapping.items():
        matched = pattern.fullmatch(pg_type)
        if matched:
            return CppType(
                typename=matched.expand(cpp_type),
                includes=['<userver/storages/postgres/io/decimal64.hpp>'],
            )

    return None


def pg_to_chrono_cpp_type(pg_type: str) -> Optional[CppType]:
    mapping = {
        'timestamp without time zone': 'storages::postgres::TimePointWithoutTz',
        'timestamp with time zone': 'storages::postgres::TimePointTz',
    }

    if pg_type in mapping:
        return CppType(
            typename=mapping[pg_type],
            includes=['<userver/storages/postgres/io/chrono.hpp>'],
        )

    return None


def pg_to_json_cpp_type(pg_type: str) -> Optional[CppType]:
    mapping = {
        'json': 'formats::json::Value',
        'jsonb': 'formats::json::Value',
    }

    if pg_type in mapping:
        return CppType(
            typename=mapping[pg_type],
            includes=['<userver/storages/postgres/io/json_types.hpp>'],
        )

    return None
