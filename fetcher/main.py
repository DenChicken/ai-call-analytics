import argparse
import logging
import sys

from src import shutdown
from src.config import ConfigError, load_config
from src.constants import DEFAULT_CONFIG_PATH, SHUTDOWN_EXIT_CODE
from src.database import Database
from src.fetch import run_once
from src.logging_setup import setup_logging
from src.sources import create_source

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch call recordings from CRM systems")
    parser.add_argument("-c", "--config", default=DEFAULT_CONFIG_PATH, help="path to TOML config")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        config = load_config(args.config)
        sources = [
            create_source(entry, config.network, config.fetch) for entry in config.sources
        ]
    except ConfigError as error:
        print(f"config error: {error}", file=sys.stderr)
        return 1

    setup_logging(config.logging)
    config.storage.pending_dir.mkdir(parents=True, exist_ok=True)
    config.storage.temp_dir.mkdir(parents=True, exist_ok=True)

    shutdown.install_handlers()

    interrupted = False
    database = Database(config.database.dsn)
    try:
        while not shutdown.is_stopping():
            for source in sources:
                try:
                    run_once(config, database, source)
                except shutdown.ShutdownRequested:
                    raise
                except Exception:
                    database.rollback()
                    logger.exception("cycle failed for source %s", source.name)
            if args.once:
                break
            shutdown.wait(config.fetch.interval_seconds)
    except shutdown.ShutdownRequested:
        interrupted = True
        logger.info("shutdown requested, stopped after last stored call")
    finally:
        database.rollback()
        for source in sources:
            source.close()
        database.close()

    return SHUTDOWN_EXIT_CODE if interrupted else 0


if __name__ == "__main__":
    sys.exit(main())
