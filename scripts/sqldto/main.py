import argparse
import logging
import pathlib
import sys

from sqldto.postgres.generator import PgGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--namespace",
        type=str,
        required=True,
        help="c++ namespace to use",
    )
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        required=True,
        help="path to the directory with .hpp-.cpp files to generate",
    )
    parser.add_argument(
        "--clang-format",
        type=str,
        default="clang-format",
        required=False,
        help="clang-format binary name. Set to empty for no formatting",
    )
    parser.add_argument(
        "--pg-migrations-dir",
        type=pathlib.Path,
        required=False,
        help="path to the directory with postgres .sql migration files",
    )
    parser.add_argument(
        "--pg-queries-dir",
        type=pathlib.Path,
        required=False,
        help="path to the directory with postgres .sql queries files",
    )
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    args = parse_args()

    namespace = args.namespace
    headers_dir = args.output_dir / "include" / namespace
    sources_dir = args.output_dir / "src" / namespace

    if args.pg_migrations_dir:
        PgGenerator(
            namespace=namespace,
            output_headers_dir=headers_dir,
            output_sources_dir=sources_dir,
            clang_format=args.clang_format,
            migrations_dir=args.pg_migrations_dir,
            queries_dir=args.pg_queries_dir,
        ).generate()


if __name__ == "__main__":
    main()
