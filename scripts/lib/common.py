import argparse
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg

MAINTENANCE_DATABASE = "postgres"


class ScriptError(Exception):
    pass


def database_exists(name: str, maintenance_dsn: str) -> bool:
    with psycopg.connect(maintenance_dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
            return cursor.fetchone() is not None


def split_dsn(dsn: str) -> tuple[str, str]:
    parts = urlsplit(dsn)
    name = parts.path.lstrip("/")
    if not name:
        raise ScriptError(f"dsn has no database name: {dsn}")
    maintenance = urlunsplit(parts._replace(path=f"/{MAINTENANCE_DATABASE}"))
    return name, maintenance


def read_dsn(path: Path) -> str:
    if not path.is_file():
        raise ScriptError(f"dsn file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        dsn = handle.readline().strip()
    if not dsn:
        raise ScriptError(f"dsn file is empty: {path}")
    return dsn


def dsn_argument_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-d",
        "--dsn-file",
        required=True,
        type=Path,
        help="path to a file whose first line is the PostgreSQL DSN",
    )
    return parser
