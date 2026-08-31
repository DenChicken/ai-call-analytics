import argparse
import logging
import sys

from src import shutdown
from src.config import Config, ConfigError, load_config
from src.constants import SHUTDOWN_EXIT_CODE
from src.database import Database
from src.fetch import run_once
from src.logging_setup import setup_logging
from src.sources import create_source

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch call recordings from CRM systems")
    parser.add_argument("-c", "--config", required=True, help="path to TOML config")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    return parser.parse_args()


def _log_startup(config: Config, once: bool) -> None:
    logger.info(
        "fetcher starting: %s sources (%s), mode=%s",
        len(config.sources),
        ", ".join(f"{entry.name}/{entry.kind}" for entry in config.sources),
        "single cycle" if once else f"every {config.fetch.interval_seconds}s",
    )
    logger.debug("fetch config: %s", config.fetch)
    logger.debug("network config: %s", config.network)
    logger.debug("storage: pending=%s temp=%s", config.storage.pending_dir, config.storage.temp_dir)


def main() -> int:
    args = parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"config error: {error}", file=sys.stderr)
        return 1

    setup_logging(config.logging)
    _log_startup(config, args.once)

    try:
        sources = [
            create_source(entry, config.network, config.fetch) for entry in config.sources
        ]
    except Exception:
        logger.exception("failed to create sources")
        return 1

    config.storage.pending_dir.mkdir(parents=True, exist_ok=True)
    config.storage.temp_dir.mkdir(parents=True, exist_ok=True)

    shutdown.install_handlers()

    try:
        database = Database(config.database.dsn)
    except Exception:
        logger.exception("failed to connect to the database")
        for source in sources:
            source.close()
        return 1

    interrupted = False
    cycle = 0
    try:
        while not shutdown.is_stopping():
            cycle += 1
            logger.debug("cycle %s started", cycle)
            for source in sources:
                try:
                    run_once(config, database, source)
                except shutdown.ShutdownRequested:
                    raise
                except Exception:
                    logger.exception("cycle failed for source %s", source.name)
            if args.once:
                break
            logger.debug("cycle %s done, sleeping %ss", cycle, config.fetch.interval_seconds)
            shutdown.wait(config.fetch.interval_seconds)
    except shutdown.ShutdownRequested:
        interrupted = True
        logger.info("shutdown requested, stopped after last stored call")
    finally:
        for source in sources:
            source.close()
        database.close()

    logger.info("fetcher %s after %s cycles", "interrupted" if interrupted else "finished", cycle)
    return SHUTDOWN_EXIT_CODE if interrupted else 0


if __name__ == "__main__":
    sys.exit(main())
