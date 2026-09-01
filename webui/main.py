import argparse
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

from licensing.constants import LICENSE_EXIT_CODE
from licensing.license import LicenseError
from licensing.verify_runtime import check, load

from src.config import Config, ConfigError, load_config
from src.constants import (
    CONFIG_ENV_VAR,
    LOG_FILE_ENV_VAR,
    PORT_PROBE_HOST,
    REFLEX_MODULE,
    REFLEX_RUN_COMMAND,
    SHUTDOWN_EXIT_CODE,
    STARTUP_ACCESS_NOTE,
    TASKKILL_COMMAND,
    TASKKILL_TREE_FLAGS,
    TERMINATE_TIMEOUT_SECONDS,
    WINDOWS_PLATFORM,
)
from src.logging_setup import new_log_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the call analytics web interface")
    parser.add_argument("-c", "--config", required=True, help="path to TOML config")
    return parser.parse_args()


def _print_startup(config: Config, log_file: Path) -> None:
    print(
        f"web interface starting: {config.server.local_url}, "
        f"backend port {config.server.backend_port}, timezone {config.display.timezone}"
    )
    print(STARTUP_ACCESS_NOTE.format(port=config.server.frontend_port))
    print(f"logs are written to {log_file}")


def _check_ports(config: Config) -> None:
    for key, port in (
        ("frontend_port", config.server.frontend_port),
        ("backend_port", config.server.backend_port),
    ):
        with socket.socket() as probe:
            try:
                probe.bind((PORT_PROBE_HOST, port))
            except OSError as error:
                raise ConfigError(
                    f"'{key}' in [server] is {port}, but that port is already in use: "
                    "stop whatever is listening on it or pick another port"
                ) from error


def _terminate_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return

    if sys.platform == WINDOWS_PLATFORM:
        subprocess.run(
            [TASKKILL_COMMAND, *TASKKILL_TREE_FLAGS, str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)

    try:
        process.wait(timeout=TERMINATE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    args = parse_args()

    try:
        config = load_config(args.config)
        _check_ports(config)
    except ConfigError as error:
        print(f"config error: {error}", file=sys.stderr)
        return 1

    try:
        check(load(config.license.file))
    except LicenseError as error:
        print(f"license error: {error}", file=sys.stderr)
        return LICENSE_EXIT_CODE

    config.logging.dir.mkdir(parents=True, exist_ok=True)
    log_file = new_log_file(config.logging.dir)
    _print_startup(config, log_file)

    environment = dict(os.environ)
    environment[CONFIG_ENV_VAR] = str(Path(args.config).resolve())
    environment[LOG_FILE_ENV_VAR] = str(log_file)

    process = subprocess.Popen(
        [sys.executable, "-m", REFLEX_MODULE, REFLEX_RUN_COMMAND],
        cwd=Path(__file__).resolve().parent,
        env=environment,
        start_new_session=sys.platform != WINDOWS_PLATFORM,
    )
    try:
        return process.wait()
    except KeyboardInterrupt:
        return SHUTDOWN_EXIT_CODE
    finally:
        _terminate_tree(process)


if __name__ == "__main__":
    sys.exit(main())
