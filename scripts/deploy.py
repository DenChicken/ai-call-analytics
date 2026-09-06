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
EXAMPLES_DIR_NAME = "examples"
SCRIPTS_DIR_NAME = "scripts"
IMAGE_PATTERN = "*.tar"

PATHS_SECTION = "paths"
SERVER_SECTION = "server"
PORT_KEY = "port"
NETWORK_SECTION = "network"
PATH_KEYS = ("data", "models", "secrets", "logs", "configs")
SUBNET_KEY = "subnet"
VERSION_KEY = "version"

MODULE_PIPELINE = "pipeline"
MODULE_WEBUI = "webui"
CONFIG_NAME = "config.toml"
DATABASE_SECTION = "database"
DSN_FILE_KEY = "dsn_file"
MODEL_SECTIONS = ("asr", "llm")
REPO_ID_KEY = "repo_id"
TOKEN_FILE_NAME = "hf_token"

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
DEFAULT_LOGIN = "admin"
FETCH_MODELS_SCRIPT = "fetch_models.py"
MODELS_DIR_FLAG = "-d"
TOKEN_FILE_FLAG = "-t"

COMMAND_INIT = "init"
COMMAND_UP = "up"

SECRETS_HINT = "the file names are listed in the module configs"
HOST_ALIAS = "host.docker.internal"
PG_LISTEN = "listen_addresses = '*'"
PG_HBA_METHOD = "scram-sha-256"
PG_DIR_LINUX = "/etc/postgresql/<version>/main"
PG_DIR_WINDOWS = r"C:\Program Files\PostgreSQL\<version>\data"


def database_access_steps(subnet: str) -> tuple[str, ...]:
    return (
        f"connection string: postgresql://user:password@{HOST_ALIAS}:5432/dbname",
        "",
        f'hosts file, add "127.0.0.1 {HOST_ALIAS}":',
        "  linux:    /etc/hosts",
        r"  windows:  C:\Windows\System32\drivers\etc\hosts",
        "",
        f"postgresql.conf, set {PG_LISTEN}",
        f"pg_hba.conf, add:  host all all {subnet} {PG_HBA_METHOD}",
        f"  linux:    {PG_DIR_LINUX}",
        f"  windows:  {PG_DIR_WINDOWS}",
        "",
        "restart PostgreSQL after the edits",
    )


class DeployError(Exception):
    pass


def shown(path: Path) -> str:
    return path.as_posix()


def python_command() -> str:
    return Path(sys.executable).name


def self_command(command: str) -> str:
    return f"{python_command()} {SELF_NAME} {command}"


def script_command(script: str, *args: str) -> str:
    return " ".join([python_command(), f"{SCRIPTS_DIR_NAME}/{script}", *args])


def read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise DeployError(f"{shown(path)} is not valid TOML: {error}") from None


def load_deploy_config() -> tuple[dict[str, Path], str]:
    config_path = ROOT / DEPLOY_CONFIG_NAME
    if not config_path.is_file():
        raise DeployError(f"{DEPLOY_CONFIG_NAME} not found next to {SELF_NAME}")

    raw = read_toml(config_path)

    for section in (PATHS_SECTION, NETWORK_SECTION):
        if section not in raw:
            raise DeployError(f"missing required section [{section}] in {DEPLOY_CONFIG_NAME}")

    paths = {}
    for key in PATH_KEYS:
        if key not in raw[PATHS_SECTION]:
            raise DeployError(f"missing required key '{key}' in [{PATHS_SECTION}]")
        value = Path(raw[PATHS_SECTION][key])
        paths[key] = value if value.is_absolute() else (ROOT / value).resolve()

    if SUBNET_KEY not in raw[NETWORK_SECTION]:
        raise DeployError(f"missing required key '{SUBNET_KEY}' in [{NETWORK_SECTION}]")
    subnet = str(raw[NETWORK_SECTION][SUBNET_KEY])

    return paths, subnet


def pipeline_config(paths: dict[str, Path]) -> dict:
    config_path = paths["configs"] / MODULE_PIPELINE / CONFIG_NAME
    if not config_path.is_file():
        raise DeployError(
            f"config not found: {shown(config_path)}, run {self_command(COMMAND_INIT)}"
        )
    return read_toml(config_path)


def webui_port(paths: dict[str, Path]) -> int:
    config_path = paths["configs"] / MODULE_WEBUI / CONFIG_NAME
    if not config_path.is_file():
        raise DeployError(
            f"config not found: {shown(config_path)}, run {self_command(COMMAND_INIT)}"
        )
    port = read_toml(config_path).get(SERVER_SECTION, {}).get(PORT_KEY)
    if not port:
        raise DeployError(f"missing '{PORT_KEY}' in [{SERVER_SECTION}] of the webui config")
    return int(port)


def dsn_path(paths: dict[str, Path]) -> Path:
    dsn_file = pipeline_config(paths).get(DATABASE_SECTION, {}).get(DSN_FILE_KEY)
    if not dsn_file:
        raise DeployError(f"missing '{DSN_FILE_KEY}' in [{DATABASE_SECTION}] of the pipeline config")
    return paths["secrets"] / dsn_file


def model_repos(paths: dict[str, Path]) -> list[str]:
    config = pipeline_config(paths)
    repos = [config.get(section, {}).get(REPO_ID_KEY) for section in MODEL_SECTIONS]
    return list(dict.fromkeys(repo for repo in repos if repo))


def run_docker(args: list[str]) -> None:
    try:
        result = subprocess.run([DOCKER, *args], cwd=ROOT, check=False)
    except FileNotFoundError:
        raise DeployError(f"{DOCKER} not found, install it and try again") from None
    if result.returncode != 0:
        raise DeployError(f"{DOCKER} {args[0]} failed with exit code {result.returncode}")


def copy_configs(configs_dir: Path) -> list[str]:
    source_root = ROOT / EXAMPLES_DIR_NAME
    if not source_root.is_dir():
        raise DeployError(f"examples not found: {shown(source_root)}")

    created = []
    for example in sorted(source_root.rglob("*")):
        if not example.is_file():
            continue
        target = configs_dir / example.relative_to(source_root)
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(example, target)
        created.append(shown(target.relative_to(configs_dir)))
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
    paths, subnet = load_deploy_config()

    for key in PATH_KEYS:
        paths[key].mkdir(parents=True, exist_ok=True)
    print(f"directories ready: {', '.join(shown(paths[key]) for key in PATH_KEYS)}")

    created = copy_configs(paths["configs"])
    if created:
        print(f"copied into {shown(paths['configs'])}: {', '.join(created)}")
    else:
        print("configs already in place, examples were not copied over them")

    load_images()
    _print_manual_steps(paths, subnet)
    return 0


def _print_manual_steps(paths: dict[str, Path], subnet: str) -> None:
    print("\nwhat is left to do by hand:\n")

    print(f"  1. secrets -> {shown(paths['secrets'])}")
    print(f"     {SECRETS_HINT}")

    print(f"\n  2. configs -> {shown(paths['configs'])}")
    print("     CRM access, scoring criteria, call types")

    print(f"\n  3. models -> {shown(paths['models'])}")
    print(
        "     "
        + script_command(
            FETCH_MODELS_SCRIPT,
            *model_repos(paths),
            MODELS_DIR_FLAG,
            shown(paths["models"]),
            TOKEN_FILE_FLAG,
            shown(paths["secrets"] / TOKEN_FILE_NAME),
        )
    )

    print("\n  4. database access")
    for line in database_access_steps(subnet):
        print(f"     {line}" if line else "")

    print(f"\nthen:  {self_command(COMMAND_UP)}")


def _print_database_access(subnet: str) -> None:
    print("\nthe database must be reachable from the containers:", file=sys.stderr)
    for line in database_access_steps(subnet):
        print(f"  {line}" if line else "", file=sys.stderr)


def check_secrets(paths: dict[str, Path]) -> None:
    secrets = paths["secrets"]
    if secrets.is_dir() and any(secrets.iterdir()):
        return
    raise DeployError(
        f"{shown(secrets)} is empty: put the license and the database connection string "
        f"there, {SECRETS_HINT}"
    )


def run_script(script: str, *args: str) -> int:
    command = [sys.executable, str(ROOT / SCRIPTS_DIR_NAME / script), *args]
    return subprocess.run(command, check=False).returncode


def apply_schema(paths: dict[str, Path], subnet: str) -> None:
    if run_script(DB_SCRIPT, DB_INIT_COMMAND, DSN_FLAG, str(dsn_path(paths))) != 0:
        _print_database_access(subnet)
        raise DeployError("could not apply the database schema")


def write_env(paths: dict[str, Path], port: int, subnet: str, version: str) -> None:
    run_as = f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else ROOT_USER
    lines = [
        f"VERSION={version}",
        f"RUN_AS={run_as}",
        f"DOCKER_SUBNET={subnet}",
        f"WEBUI_PORT={port}",
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
    paths, subnet = load_deploy_config()
    port = webui_port(paths)

    check_secrets(paths)
    apply_schema(paths, subnet)
    write_env(paths, port, subnet, read_version())
    run_docker([*COMPOSE_ARGS, str(ROOT / COMPOSE_NAME), *UP_ARGS])

    print(f"\nweb interface: http://localhost:{port}")
    print("if there are no users yet, create the first one:")
    print(
        "  "
        + script_command(
            USER_SCRIPT, USER_ADD_COMMAND, DEFAULT_LOGIN, DSN_FLAG, shown(dsn_path(paths))
        )
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
