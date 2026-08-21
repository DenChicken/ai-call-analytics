import argparse
import getpass
import sys
from pathlib import Path

import psycopg
from argon2 import PasswordHasher

PASSWORD_PROMPT = "password: "
PASSWORD_CONFIRM_PROMPT = "repeat password: "
MIN_PASSWORD_LENGTH = 8

COMMAND_ADD = "add"
COMMAND_PASSWD = "passwd"
COMMAND_LIST = "list"
COMMAND_DELETE = "delete"


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


def ask_password() -> str:
    try:
        password = getpass.getpass(PASSWORD_PROMPT)
        repeated = getpass.getpass(PASSWORD_CONFIRM_PROMPT)
    except (EOFError, KeyboardInterrupt):
        raise ScriptError("aborted")
    if password != repeated:
        raise ScriptError("passwords do not match")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ScriptError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    return password


def command_add(connection, login: str) -> int:
    password_hash = PasswordHasher().hash(ask_password())
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (login, password_hash) VALUES (%s, %s) "
            "ON CONFLICT (login) DO NOTHING RETURNING id",
            (login, password_hash),
        )
        if cursor.fetchone() is None:
            raise ScriptError(f"user '{login}' already exists, use passwd to change the password")
    connection.commit()
    print(f"user '{login}' created")
    return 0


def command_passwd(connection, login: str) -> int:
    password_hash = PasswordHasher().hash(ask_password())
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE login = %s RETURNING id",
            (password_hash, login),
        )
        if cursor.fetchone() is None:
            raise ScriptError(f"user '{login}' not found")
    connection.commit()
    print(f"password for '{login}' changed")
    return 0


def command_list(connection, login: str | None) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT login, created_at FROM users ORDER BY login")
        rows = cursor.fetchall()
    if not rows:
        print("no users, create one with add")
        return 0
    for row in rows:
        print(f"{row[0]}\t{row[1]:%Y-%m-%d %H:%M}")
    return 0


def command_delete(connection, login: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE login = %s RETURNING id", (login,))
        if cursor.fetchone() is None:
            raise ScriptError(f"user '{login}' not found")
        cursor.execute("SELECT count(*) FROM users")
        remaining = cursor.fetchone()[0]
    connection.commit()
    print(f"user '{login}' deleted, {remaining} left")
    if not remaining:
        print("no users left, nobody can sign in until you add one", file=sys.stderr)
    return 0


COMMANDS = {
    COMMAND_ADD: command_add,
    COMMAND_PASSWD: command_passwd,
    COMMAND_LIST: command_list,
    COMMAND_DELETE: command_delete,
}

COMMANDS_WITH_LOGIN = (COMMAND_ADD, COMMAND_PASSWD, COMMAND_DELETE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage web interface users")
    parser.add_argument(
        "command",
        choices=sorted(COMMANDS),
        help=(
            "add: create a user and set the password; "
            "passwd: change the password of an existing user; "
            "list: show all users; "
            "delete: remove a user"
        ),
    )
    parser.add_argument("login", nargs="?", help="user login")
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

    if args.command in COMMANDS_WITH_LOGIN and not args.login:
        print(f"{args.command} requires a login", file=sys.stderr)
        return 1

    try:
        with psycopg.connect(read_dsn(args.dsn_file)) as connection:
            return COMMANDS[args.command](connection, args.login)
    except ScriptError as error:
        print(error, file=sys.stderr)
        return 1
    except psycopg.Error as error:
        print(f"{args.command} failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
