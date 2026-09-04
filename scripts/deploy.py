import argparse
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SELF_NAME = Path(__file__).name

DEPLOY_CONFIG_NAME = "deploy.toml"
ENV_NAME = ".env"
COMPOSE_NAME = "compose.yaml"
MANIFEST_NAME = "manifest.json"
IMAGES_DIR_NAME = "images"
CONFIGS_DIR_NAME = "configs"
SCRIPTS_DIR_NAME = "scripts"
IMAGE_PATTERN = "*.tar"

PATHS_SECTION = "paths"
SERVER_SECTION = "server"
PATH_KEYS = ("data", "models", "secrets", "logs")
PORT_KEYS = ("frontend_port", "backend_port")
VERSION_KEY = "version"

MODULE_PIPELINE = "pipeline"
CONFIG_NAME = "config.toml"
CONFIG_TEMPLATE_SUFFIX = ".template"
DATABASE_SECTION = "database"
DSN_FILE_KEY = "dsn_file"

DOCKER = "docker"
ROOT_USER = "0:0"
LOAD_ARGS = ("load", "-i")
COMPOSE_ARGS = ("compose", "-f")
UP_ARGS = ("up", "-d")

DB_SCRIPT = "db.py"
DB_INIT_COMMAND = "init"
DSN_FLAG = "-d"
USER_SCRIPT = "user.py"
USER_ADD_COMMAND = "add"
FETCH_MODELS_SCRIPT = "fetch_models.py"
CONFIG_FLAG = "-c"

COMMAND_INIT = "init"
COMMAND_UP = "up"

SECRETS_HINT = "the file names are listed in {configs}/*/{config}"


class DeployError(Exception):
    pass


def shown(path: Path) -> str:
    return path.as_posix()


def python_command() -> str:
    return Path(sys.executable).name


def self_command(command: str) -> str:
    return f"{python_command()} {SELF_NAME} {command}"


def secrets_hint() -> str:
    return SECRETS_HINT.format(configs=CONFIGS_DIR_NAME, config=CONFIG_NAME)


def load_deploy_config() -> tuple[dict[str, Path], dict[str, int]]:
    config_path = ROOT / DEPLOY_CONFIG_NAME
    if not config_path.is_file():
        raise DeployError(f"{DEPLOY_CONFIG_NAME} not found next to {SELF_NAME}")

    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    for section in (PATHS_SECTION, SERVER_SECTION):
        if section not in raw:
            raise DeployError(f"missing required section [{section}] in {DEPLOY_CONFIG_NAME}")

    paths = {}
    for key in PATH_KEYS:
        if key not in raw[PATHS_SECTION]:
            raise DeployError(f"missing required key '{key}' in [{PATHS_SECTION}]")
        value = Path(raw[PATHS_SECTION][key])
        paths[key] = value if value.is_absolute() else (ROOT / value).resolve()

    ports = {}
    for key in PORT_KEYS:
        if key not in raw[SERVER_SECTION]:
            raise DeployError(f"missing required key '{key}' in [{SERVER_SECTION}]")
        ports[key] = int(raw[SERVER_SECTION][key])

    return paths, ports


def dsn_path(paths: dict[str, Path]) -> Path:
    config_path = ROOT / CONFIGS_DIR_NAME / MODULE_PIPELINE / CONFIG_NAME
    if not config_path.is_file():
        raise DeployError(
            f"config not found: {shown(config_path)}, run {self_command(COMMAND_INIT)}"
        )

    with config_path.open("rb") as handle:
        dsn_file = tomllib.load(handle).get(DATABASE_SECTION, {}).get(DSN_FILE_KEY)
    if not dsn_file:
        raise DeployError(
            f"missing '{DSN_FILE_KEY}' in [{DATABASE_SECTION}] of {shown(config_path)}"
        )
    return paths["secrets"] / dsn_file


def run_docker(args: list[str]) -> None:
    try:
        result = subprocess.run([DOCKER, *args], cwd=ROOT, check=False)
    except FileNotFoundError:
        raise DeployError(f"{DOCKER} not found, install it and try again") from None
    if result.returncode != 0:
        raise DeployError(f"{DOCKER} {args[0]} failed with exit code {result.returncode}")


def copy_configs() -> list[str]:
    source_root = ROOT / CONFIGS_DIR_NAME
    if not source_root.is_dir():
        raise DeployError(f"configs not found: {shown(source_root)}")

    created = []
    for template in sorted(source_root.rglob(f"*{CONFIG_TEMPLATE_SUFFIX}")):
        target = template.with_name(template.name[: -len(CONFIG_TEMPLATE_SUFFIX)])
        if target.exists():
            continue
        shutil.copy2(template, target)
        created.append(shown(target.relative_to(ROOT)))
    return created


def load_images() -> None:
    images_dir = ROOT / IMAGES_DIR_NAME
    archives = sorted(images_dir.glob(IMAGE_PATTERN)) if images_dir.is_dir() else []
    if not archives:
        raise DeployError(f"no images found in {shown(images_dir)}")

    for archive in archives:
        print(f"loading {archive.name}", flush=True)
        run_docker([*LOAD_ARGS, str(archive)])


def command_init() -> int:
    paths, _ = load_deploy_config()

    for key in PATH_KEYS:
        paths[key].mkdir(parents=True, exist_ok=True)
    print(f"directories ready: {', '.join(shown(paths[key]) for key in PATH_KEYS)}")

    created = copy_configs()
    print(f"created configs: {', '.join(created)}" if created else "configs already in place")

    load_images()

    print("\nwhat is left to do by hand:\n")
    print(f"  1. put the license and the database connection string into {shown(paths['secrets'])}")
    print(f"     {secrets_hint()}")
    print(f"\n  2. adjust {CONFIGS_DIR_NAME}/ to your setup: CRM access, criteria, call types")
    print(f"\n  3. put the models into {shown(paths['models'])} or download them:")
    print(
        f"       {python_command()} {SCRIPTS_DIR_NAME}/{FETCH_MODELS_SCRIPT} "
        f"{CONFIG_FLAG} {CONFIGS_DIR_NAME}/{MODULE_PIPELINE}/{CONFIG_NAME}"
    )
    print(f"\nthen:  {self_command(COMMAND_UP)}")
    return 0


def check_secrets(paths: dict[str, Path]) -> None:
    secrets = paths["secrets"]
    if secrets.is_dir() and any(secrets.iterdir()):
        return
    raise DeployError(
        f"{shown(secrets)} is empty: put the license and the database connection string "
        f"there, {secrets_hint()}"
    )


def apply_schema(paths: dict[str, Path]) -> None:
    command = [
        sys.executable,
        str(ROOT / SCRIPTS_DIR_NAME / DB_SCRIPT),
        DB_INIT_COMMAND,
        DSN_FLAG,
        str(dsn_path(paths)),
    ]
    if subprocess.run(command, check=False).returncode != 0:
        raise DeployError("could not apply the database schema")


def write_env(paths: dict[str, Path], ports: dict[str, int], version: str) -> None:
    run_as = f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else ROOT_USER
    lines = [
        f"VERSION={version}",
        f"RUN_AS={run_as}",
        f"CONFIGS_DIR={shown(ROOT / CONFIGS_DIR_NAME)}",
        f"FRONTEND_PORT={ports['frontend_port']}",
        f"BACKEND_PORT={ports['backend_port']}",
    ]
    lines += [f"{key.upper()}_DIR={shown(paths[key])}" for key in PATH_KEYS]
    (ROOT / ENV_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_version() -> str:
    manifest_path = ROOT / MANIFEST_NAME
    if not manifest_path.is_file():
        raise DeployError(f"{MANIFEST_NAME} not found, the bundle is incomplete")

    with manifest_path.open("r", encoding="utf-8") as handle:
        version = json.load(handle).get(VERSION_KEY)
    if not version:
        raise DeployError(f"no version recorded in {MANIFEST_NAME}")
    return version


def command_up() -> int:
    paths, ports = load_deploy_config()

    check_secrets(paths)
    apply_schema(paths)
    write_env(paths, ports, read_version())
    run_docker([*COMPOSE_ARGS, str(ROOT / COMPOSE_NAME), *UP_ARGS])

    print(f"\nweb interface: http://localhost:{ports['frontend_port']}")
    print("if there are no users yet, create the first one:")
    print(
        f"  {python_command()} {SCRIPTS_DIR_NAME}/{USER_SCRIPT} {USER_ADD_COMMAND} "
        f"{DSN_FLAG} {shown(dsn_path(paths))} --username admin"
    )
    print(f"\nservice state and logs, from {shown(ROOT)}:")
    print(f"  {DOCKER} compose ps")
    print(f"  {DOCKER} compose logs -f")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy ai-call-analytics")
    parser.add_argument(
        "command",
        choices=(COMMAND_INIT, COMMAND_UP),
        help="init prepares the host, up applies the schema and starts the services",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return command_init() if args.command == COMMAND_INIT else command_up()
    except DeployError as error:
        print(f"deploy error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
