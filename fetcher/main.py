import argparse
import logging
import sys

from licensing.constants import LICENSE_EXIT_CODE
from licensing.license import LicenseError
from licensing.verify_runtime import check, is_expired, load

from src import shutdown
from src.config import Config, ConfigError, load_config
from src.constants import (
    SHUTDOWN_EXIT_CODE,
    UNRECOVERABLE_EXIT_CODE,
)
from src.database import Database
from src.errors import UnrecoverableError
from src.fetch import run_once
from src.logging_setup import setup_logging
from src.sources import create_source

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch call recordings from CRM systems")
    parser.add_argument("-c", "--config", required=True, help="path to TOML config")
    return parser.parse_args()


def _log_startup(config: Config) -> None:
    logger.info(
        "fetcher starting: %s sources (%s), every %ss",
        len(config.sources),
        ", ".join(f"{entry.name}/{entry.kind}" for entry in config.sources),
        config.fetch.interval_seconds,
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
    _log_startup(config)

    try:
        license = load(config.license.file)
        check(license)
    except LicenseError as error:
        print(f"license error: {error}", file=sys.stderr)
        logger.error("license check failed: %s", error)
        return LICENSE_EXIT_CODE
    logger.info("license valid until %s", license.expires)

    try:
        sources = [
            create_source(entry, config.network, config.fetch) for entry in config.sources
        ]
    except ConfigError as error:
        print(f"config error: {error}", file=sys.stderr)
        logger.error("config error: %s", error)
        return 1
    except Exception:
        logger.exception("failed to create sources")
        return 1

    config.storage.pending_dir.mkdir(parents=True, exist_ok=True)
    config.storage.temp_dir.mkdir(parents=True, exist_ok=True)

    shutdown.install_handlers()

    try:
        database = Database(config.database)
    except Exception as error:
        print(f"cannot start: the database is unreachable: {error}", file=sys.stderr)
        logger.error("cannot start: the database is unreachable: %s", error)
        for source in sources:
            source.close()
        return UNRECOVERABLE_EXIT_CODE

    expired = False
    cycle = 0
    try:
        while not shutdown.is_stopping():
            if is_expired(license):
                expired = True
                logger.error("license expired on %s, stopping", license.expires)
                shutdown.request_stop()
                break
            cycle += 1
            logger.debug("cycle %s started", cycle)
            served = 0
            for source in sources:
                try:
                    run_once(config, database, source)
                except shutdown.ShutdownRequested:
                    raise
                except UnrecoverableError as error:
                    logger.error("source %s cannot be served: %s", source.name, error)
                except Exception:
                    served += 1
                    logger.exception("cycle failed for source %s", source.name)
                else:
                    served += 1

            if not served:
                logger.error("cycle %s served no source, none of them can be used", cycle)
            logger.debug("cycle %s done, sleeping %ss", cycle, config.fetch.interval_seconds)
            shutdown.sleep(config.fetch.interval_seconds)
    except shutdown.ShutdownRequested:
        logger.info("shutdown requested, stopped after last stored call")
    finally:
        for source in sources:
            source.close()
        database.close()

    if expired:
        logger.info("fetcher stopped after %s cycles: license expired", cycle)
        return LICENSE_EXIT_CODE
    logger.info("fetcher stopped after %s cycles", cycle)
    return SHUTDOWN_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
