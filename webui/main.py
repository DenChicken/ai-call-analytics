import argparse
import os
import subprocess
import sys
from pathlib import Path

from src.config import Config, ConfigError, load_config
from src.constants import (
    CONFIG_ENV_VAR,
    LOG_FILE_ENV_VAR,
    REFLEX_MODULE,
    REFLEX_RUN_COMMAND,
)
from src.logging_setup import new_log_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the call analytics web interface")
    parser.add_argument("-c", "--config", required=True, help="path to TOML config")
    return parser.parse_args()


def _print_startup(config: Config, log_file: Path) -> None:
    print(
        f"web interface starting: frontend {config.server.frontend_url}, "
        f"backend {config.server.api_url}, timezone {config.display.timezone}"
    )
    print(f"logs are written to {log_file}")


def main() -> int:
    args = parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"config error: {error}", file=sys.stderr)
        return 1

    config.logging.dir.mkdir(parents=True, exist_ok=True)
    log_file = new_log_file(config.logging.dir)
    _print_startup(config, log_file)

    environment = dict(os.environ)
    environment[CONFIG_ENV_VAR] = str(Path(args.config).resolve())
    environment[LOG_FILE_ENV_VAR] = str(log_file)

    try:
        completed = subprocess.run(
            [sys.executable, "-m", REFLEX_MODULE, REFLEX_RUN_COMMAND],
            cwd=Path(__file__).resolve().parent,
            env=environment,
        )
    except KeyboardInterrupt:
        return 0

    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
