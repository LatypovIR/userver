import argparse
import pathlib

from postgres.generator import PgGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--namespace',
        type=str,
        required=True,
        help='C++ namespace to use',
    )
    parser.add_argument(
        '--output-dir',
        type=pathlib.Path,
        required=True,
        help='path to the directory with .hpp-.cpp files to generate',
    )
    parser.add_argument(
        '--pg-namespace',
        type=pathlib.Path,
        required=False,
        help='C++ namespace to use in postgres',
    )
    parser.add_argument(
        '--pg-migrations-dir',
        type=pathlib.Path,
        required=False,
        help='path to the directory with postgres .sql migration files',
    )
    parser.add_argument(
        '--pg-queries-dir',
        type=pathlib.Path,
        required=False,
        help='path to the directory with postgres .sql queries files',
    )
    return parser.parse_args()


def main():
    args = parse_args()

    namespace = args.namespace
    headers_dir = args.output_dir / 'include' / namespace

    if args.pg_migrations_dir:
        pg_namespace = namespace
        pg_headers_dir = headers_dir
        if args.pg_namespace:
            pg_namespace += f'::{args.pg_namespace}'
            pg_headers_dir /= args.pg_namespace

        PgGenerator(
            namespace=pg_namespace,
            output_dir=pg_headers_dir,
            migrations_dir=args.pg_migrations_dir,
            queries_dir=args.pg_queries_dir,
        ).generate()


if __name__ == '__main__':
    main()
