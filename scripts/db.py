import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"
PASSWORD_PROMPT = "database password: "
MAINTENANCE_DATABASE = "postgres"

COMMAND_INIT = "init"
COMMAND_CLEAR = "clear"
COMMAND_DROP = "drop"
COMMAND_RESET = "reset"


class ScriptError(Exception):
    pass


def read_dsn(path: Path) -> str:
    if not path.is_file():
        raise ScriptError(f"dsn file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        dsn = handle.readline().strip()
    if not dsn:
        raise ScriptError(f"dsn file is empty: {path}")
    return dsn


class Database:
    def __init__(self, dsn: str):
        parts = urlsplit(dsn)
        name = parts.path.lstrip("/")
        if not name:
            raise ScriptError(f"dsn has no database name: {dsn}")
        self.dsn = dsn
        self.name = name
        self.maintenance_dsn = urlunsplit(parts._replace(path=f"/{MAINTENANCE_DATABASE}"))

    def exists(self) -> bool:
        with psycopg.connect(self.maintenance_dsn, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (self.name,))
                return cursor.fetchone() is not None

    def create(self) -> None:
        self._run_maintenance(f'CREATE DATABASE "{self.name}"')

    def drop(self) -> None:
        self._run_maintenance(f'DROP DATABASE "{self.name}" WITH (FORCE)')

    def tables(self) -> list[str]:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
                )
                return [row[0] for row in cursor.fetchall()]

    def apply_schema(self) -> None:
        if not SCHEMA_FILE.is_file():
            raise ScriptError(f"schema file not found: {SCHEMA_FILE}")
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(SCHEMA_FILE.read_text(encoding="utf-8"))

    def truncate(self, tables: list[str]) -> int:
        with psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                counts = " + ".join(f"(SELECT count(*) FROM {table})" for table in tables)
                cursor.execute(f"SELECT {counts}")
                total = cursor.fetchone()[0]
                cursor.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")
        return total

    def _run_maintenance(self, statement: str) -> None:
        with psycopg.connect(self.maintenance_dsn, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement)


def confirm(dsn: str, warning: str) -> bool:
    expected = urlsplit(dsn).password
    if not expected:
        raise ScriptError("dsn has no password, refusing to run a destructive command")

    print(warning)
    try:
        matched = input(PASSWORD_PROMPT).strip() == expected
    except (EOFError, KeyboardInterrupt):
        print("aborted", file=sys.stderr)
        return False
    if not matched:
        print("password does not match, nothing was changed", file=sys.stderr)
    return matched


def command_init(database: Database) -> int:
    if not database.exists():
        database.create()
        print(f"database {database.name} created")
    database.apply_schema()
    print(f"schema applied from {SCHEMA_FILE}")
    return 0


def command_clear(database: Database) -> int:
    if not database.exists():
        raise ScriptError(f"database {database.name} does not exist, nothing to clear")

    tables = database.tables()
    if not tables:
        raise ScriptError(f"database {database.name} has no tables, nothing to clear")

    if not confirm(
        database.dsn,
        f"about to delete all rows from {database.name}: {', '.join(tables)}\n"
        "tables themselves are kept, no need to run init afterwards",
    ):
        return 1

    total = database.truncate(tables)
    if total:
        print(f"deleted {total} rows, schema kept")
        print("audio files on disk are untouched and are now orphaned")
    else:
        print("database was already empty, schema kept")
    return 0


def command_drop(database: Database) -> int:
    if not database.exists():
        raise ScriptError(f"database {database.name} does not exist, nothing to drop")

    if not confirm(
        database.dsn,
        f"about to DROP database {database.name} entirely\n"
        "all calls, transcripts and analyses will be lost",
    ):
        return 1

    database.drop()
    print(f"database {database.name} dropped")
    return 0


def command_reset(database: Database) -> int:
    if database.exists():
        if command_drop(database) != 0:
            return 1
    return command_init(database)


COMMANDS = {
    COMMAND_INIT: command_init,
    COMMAND_CLEAR: command_clear,
    COMMAND_DROP: command_drop,
    COMMAND_RESET: command_reset,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the call analytics database")
    parser.add_argument(
        "command",
        choices=sorted(COMMANDS),
        help=(
            "init: create the database if missing and apply the schema; "
            "clear: delete all rows, keep the schema; "
            "drop: delete the database entirely; "
            "reset: drop and initialize from scratch"
        ),
    )
    parser.add_argument(
        "-d",
        "--dsn-file",
        required=True,
        type=Path,
        help="path to a file whose first line is the PostgreSQL DSN",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        database = Database(read_dsn(args.dsn_file))
        return COMMANDS[args.command](database)
    except ScriptError as error:
        print(error, file=sys.stderr)
        return 1
    except psycopg.Error as error:
        print(f"{args.command} failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
