import sys
from urllib.parse import urlsplit

import psycopg

from lib.common import (
    ScriptError,
    database_exists,
    dsn_argument_parser,
    read_dsn,
    split_dsn,
)

TABLES = (
    "criterion_scores",
    "transcript_segments",
    "analyses",
    "recordings",
    "calls",
    "agents",
    "sources",
)
PROMPT = "database password: "


def confirm_password(dsn: str) -> bool:
    expected = urlsplit(dsn).password
    if not expected:
        print("dsn has no password, refusing to run", file=sys.stderr)
        return False
    try:
        return input(PROMPT).strip() == expected
    except (EOFError, KeyboardInterrupt):
        print("aborted", file=sys.stderr)
        return False


def main() -> int:
    args = dsn_argument_parser(
        "Delete all rows from the call analytics tables. Schema is kept."
    ).parse_args()

    try:
        dsn = read_dsn(args.dsn_file)
        name, maintenance_dsn = split_dsn(dsn)
        if not database_exists(name, maintenance_dsn):
            print(f"database {name} does not exist, nothing to clear", file=sys.stderr)
            return 1
    except (ScriptError, psycopg.Error) as error:
        print(error, file=sys.stderr)
        return 1

    print(f"about to delete all rows from {name}: {', '.join(TABLES)}")
    print("tables themselves are kept, no need to run init_db afterwards")
    if not confirm_password(dsn):
        print("password does not match, nothing was changed", file=sys.stderr)
        return 1

    try:
        with psycopg.connect(dsn) as connection:
            with connection.cursor() as cursor:
                counts = " + ".join(f"(SELECT count(*) FROM {table})" for table in TABLES)
                cursor.execute(f"SELECT {counts}")
                total = cursor.fetchone()[0]
                cursor.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")
    except psycopg.Error as error:
        print(f"failed to clear database: {error}", file=sys.stderr)
        return 1

    if total:
        print(f"deleted {total} rows, schema kept")
        print("audio files on disk are untouched and are now orphaned")
    else:
        print("database was already empty, schema kept")
    return 0


if __name__ == "__main__":
    sys.exit(main())
