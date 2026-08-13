import sys
from pathlib import Path

import psycopg

from lib.common import (
    ScriptError,
    database_exists,
    dsn_argument_parser,
    read_dsn,
    split_dsn,
)

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def create_database_if_missing(name: str, maintenance_dsn: str) -> bool:
    if database_exists(name, maintenance_dsn):
        return False
    with psycopg.connect(maintenance_dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{name}"')
    return True


def main() -> int:
    args = dsn_argument_parser(
        "Create the call analytics schema. Safe to run repeatedly."
    ).parse_args()

    try:
        dsn = read_dsn(args.dsn_file)
        name, maintenance_dsn = split_dsn(dsn)
    except ScriptError as error:
        print(error, file=sys.stderr)
        return 1

    if not SCHEMA_FILE.is_file():
        print(f"schema file not found: {SCHEMA_FILE}", file=sys.stderr)
        return 1

    try:
        if create_database_if_missing(name, maintenance_dsn):
            print(f"database {name} created")
        with psycopg.connect(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
    except psycopg.Error as error:
        print(f"failed to apply schema: {error}", file=sys.stderr)
        return 1

    print(f"schema applied from {SCHEMA_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
