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
COMPOSE_GPU_NAME = "compose.gpu.yaml"
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

MODULE_FETCHER = "fetcher"
MODULE_PIPELINE = "pipeline"
MODULE_WEBUI = "webui"
MODULES = (MODULE_FETCHER, MODULE_PIPELINE, MODULE_WEBUI)
CONFIG_NAME = "config.toml"
DATABASE_SECTION = "database"
DSN_FILE_KEY = "dsn_file"
ASR_SECTION = "asr"
LLM_SECTION = "llm"
REPO_ID_KEY = "repo_id"
MODEL_FILE_KEY = "model_file"
MODEL_FILE_SEPARATOR = ":"
DEVICE_KEY = "device"
DEVICE_CUDA = "cuda"
GPU_LAYERS_KEY = "gpu_layers"
GPU_LAYERS_NONE = "none"
TOKEN_FILE_NAME = "hf_token"

DOCKER = "docker"
ROOT_USER = "0:0"
LOG_TAIL_LINES = "100"
LOAD_ARGS = ("load", "-i")
COMPOSE_COMMAND = "compose"
COMPOSE_FILE_FLAG = "-f"

DB_SCRIPT = "db.py"
DB_INIT_COMMAND = "init"
DSN_FLAG = "-d"
USER_SCRIPT = "user.py"
USER_ADD_COMMAND = "add"
DEFAULT_LOGIN = "admin"
FETCH_MODELS_SCRIPT = "fetch_models.py"
PLATFORM_DIR_NAME = "platform"
PLATFORM_UBUNTU = "ubuntu"
NVIDIA_DRIVER_SCRIPT = "install_nvidia_driver.sh"
NVIDIA_TOOLKIT_SCRIPT = "install_nvidia_docker_tools.sh"
MODELS_DIR_FLAG = "-d"
TOKEN_FILE_FLAG = "-t"

COMMAND_INIT = "init"
COMMAND_UP = "up"
COMMAND_STOP = "stop"
COMMAND_RESTART = "restart"
COMMAND_LOGS = "logs"

COMPOSE_COMMANDS = {
    COMMAND_UP: ("up", "-d"),
    COMMAND_STOP: ("stop",),
    COMMAND_RESTART: ("restart",),
    COMMAND_LOGS: ("logs", "-f", "--tail", LOG_TAIL_LINES),
}

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


def gpu_access_steps() -> tuple[str, ...]:
    return (
        "the host needs the nvidia driver and the container toolkit:",
        f"  {platform_script(NVIDIA_DRIVER_SCRIPT)}",
        "  sudo reboot",
        f"  {platform_script(NVIDIA_TOOLKIT_SCRIPT)}",
        "",
        "the toolkit script ends with a check that the card reaches a container",
    )


class DeployError(Exception):
    pass


def shown(path: Path) -> str:
    return path.as_posix()


def python_command() -> str:
    return Path(sys.executable).name


def self_command(command: str) -> str:
    return f"{python_command()} {SELF_NAME} {command}"


def platform_script(name: str) -> str:
    return f"{SCRIPTS_DIR_NAME}/{PLATFORM_DIR_NAME}/{PLATFORM_UBUNTU}/{name}"


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


def module_config(paths: dict[str, Path], module: str) -> dict:
    config_path = paths["configs"] / module / CONFIG_NAME
    if not config_path.is_file():
        raise DeployError(
            f"config not found: {shown(config_path)}, run {self_command(COMMAND_INIT)}"
        )
    return read_toml(config_path)


def webui_port(paths: dict[str, Path]) -> int:
    port = module_config(paths, MODULE_WEBUI).get(SERVER_SECTION, {}).get(PORT_KEY)
    if not port:
        raise DeployError(f"missing '{PORT_KEY}' in [{SERVER_SECTION}] of the webui config")
    return int(port)


def dsn_path(paths: dict[str, Path]) -> Path:
    dsn_file = (
        module_config(paths, MODULE_PIPELINE).get(DATABASE_SECTION, {}).get(DSN_FILE_KEY)
    )
    if not dsn_file:
        raise DeployError(f"missing '{DSN_FILE_KEY}' in [{DATABASE_SECTION}] of the pipeline config")
    return paths["secrets"] / dsn_file


def wants_gpu(paths: dict[str, Path]) -> bool:
    config = module_config(paths, MODULE_PIPELINE)
    if config.get(ASR_SECTION, {}).get(DEVICE_KEY) == DEVICE_CUDA:
        return True
    llm = config.get(LLM_SECTION, {})
    if GPU_LAYERS_KEY not in llm:
        raise DeployError(f"missing '{GPU_LAYERS_KEY}' in [{LLM_SECTION}] of the pipeline config")
    layers = str(llm[GPU_LAYERS_KEY])
    if layers == GPU_LAYERS_NONE:
        return False
    return not (layers.isdigit() and int(layers) == 0)


def model_repos(paths: dict[str, Path]) -> list[str]:
    config = module_config(paths, MODULE_PIPELINE)
    asr = config.get(ASR_SECTION, {}).get(REPO_ID_KEY)
    llm = config.get(LLM_SECTION, {})
    targets = [asr]
    if llm.get(REPO_ID_KEY) and llm.get(MODEL_FILE_KEY):
        targets.append(f"{llm[REPO_ID_KEY]}{MODEL_FILE_SEPARATOR}{llm[MODEL_FILE_KEY]}")
    return list(dict.fromkeys(target for target in targets if target))


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

    print(f"\n  5. gpu, only if the pipeline config asks for {DEVICE_CUDA}")
    for line in gpu_access_steps():
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


def run_compose(command: str, modules: list[str], gpu: bool) -> None:
    files = [COMPOSE_FILE_FLAG, str(ROOT / COMPOSE_NAME)]
    if gpu:
        files += [COMPOSE_FILE_FLAG, str(ROOT / COMPOSE_GPU_NAME)]
    run_docker([COMPOSE_COMMAND, *files, *COMPOSE_COMMANDS[command], *modules])


def command_compose(command: str, modules: list[str]) -> int:
    paths, subnet = load_deploy_config()
    port = webui_port(paths)

    starting = command == COMMAND_UP
    if starting:
        check_secrets(paths)
        apply_schema(paths, subnet)

    write_env(paths, port, subnet, read_version())
    run_compose(command, modules, wants_gpu(paths))

    if starting and (not modules or MODULE_WEBUI in modules):
        _print_running(paths, port)
    return 0


def _print_running(paths: dict[str, Path], port: int) -> None:
    print(f"\nweb interface: http://localhost:{port}")
    print("if there are no users yet, create the first one:")
    print(
        "  "
        + script_command(
            USER_SCRIPT, USER_ADD_COMMAND, DEFAULT_LOGIN, DSN_FLAG, shown(dsn_path(paths))
        )
    )
    print(f"\nservice state, from {shown(ROOT)}:")
    print(f"  {DOCKER} compose ps")
    print(f"  {self_command(COMMAND_LOGS)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy speech-analysis-engine")
    parser.add_argument(
        "command",
        choices=(COMMAND_INIT, *COMPOSE_COMMANDS),
        help=(
            "init prepares the host; "
            "up applies the schema and starts the services; "
            "stop, restart and logs act on running services"
        ),
    )
    parser.add_argument(
        "modules",
        nargs="*",
        metavar="module",
        help=f"modules to act on, all of them when omitted: {', '.join(MODULES)}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    unknown = [module for module in args.modules if module not in MODULES]
    if unknown:
        print(
            f"unknown module: {', '.join(unknown)}, expected one of: {', '.join(MODULES)}",
            file=sys.stderr,
        )
        return 1
    if args.command == COMMAND_INIT and args.modules:
        print(f"{COMMAND_INIT} prepares the whole host and takes no modules", file=sys.stderr)
        return 1
    try:
        if args.command == COMMAND_INIT:
            return command_init()
        return command_compose(args.command, args.modules)
    except DeployError as error:
        print(f"deploy error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
