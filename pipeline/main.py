import argparse
import logging
import sys

from licensing.constants import LICENSE_EXIT_CODE
from licensing.license import LicenseError
from licensing.verify_runtime import check, load

from src import shutdown
from src.asr import Asr
from src.config import Config, ConfigError, load_config
from src.constants import (
    CALL_TYPES_TABLE,
    CRITERIA_TABLE,
    SHUTDOWN_EXIT_CODE,
    UNRECOVERABLE_EXIT_CODE,
)
from src.database import Database
from src.errors import UnrecoverableError
from src.llm import Llm
from src.logging_setup import setup_logging
from src.worker import run

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe and analyze call recordings")
    parser.add_argument("-c", "--config", required=True, help="path to TOML config")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"config error: {error}", file=sys.stderr)
        return 1

    setup_logging(config.logging)
    _log_startup(config)
    config.storage.done_dir.mkdir(parents=True, exist_ok=True)

    try:
        license = load(config.license.file)
        check(license)
    except LicenseError as error:
        print(f"license error: {error}", file=sys.stderr)
        logger.error("license check failed: %s", error)
        return LICENSE_EXIT_CODE
    logger.info("license valid until %s", license.expires)

    shutdown.install_handlers()

    database = None
    try:
        database = Database(config.database)
        for table, entries in (
            (CRITERIA_TABLE, config.criteria),
            (CALL_TYPES_TABLE, config.call_types),
        ):
            disabled = database.sync_reference(table, entries)
            logger.info("%s synced: %s enabled, %s disabled", table, len(entries), disabled)

        asr = Asr(config.asr)
        llm = Llm(config.llm)
    except UnrecoverableError as error:
        print(f"cannot start: {error}", file=sys.stderr)
        logger.error("cannot start: %s", error)
        if database is not None:
            database.close()
        return UNRECOVERABLE_EXIT_CODE
    except Exception:
        logger.exception("cannot start: initialization failed")
        if database is not None:
            database.close()
        return UNRECOVERABLE_EXIT_CODE

    expired = False
    unusable = False
    try:
        run(config, database, asr, llm, license)
    except shutdown.LicenseExpired:
        expired = True
    except shutdown.ShutdownRequested:
        pass
    except UnrecoverableError as error:
        logger.error("pipeline stopping, the queue is untouched: %s", error)
        unusable = True
    except Exception:
        logger.exception("pipeline crashed")
        unusable = True
    finally:
        database.close()

    if unusable:
        return UNRECOVERABLE_EXIT_CODE
    if expired:
        logger.info("pipeline stopped: license expired")
        return LICENSE_EXIT_CODE
    logger.info("pipeline stopped on request")
    return SHUTDOWN_EXIT_CODE


def _log_startup(config: Config) -> None:
    logger.info(
        "pipeline starting: asr=%s llm=%s prompt=%s",
        config.asr.repo_id,
        config.llm.repo_id,
        config.prompt.label,
    )
    logger.debug("asr config: %s", config.asr)
    logger.debug("llm config: %s", config.llm)
    logger.debug("worker config: %s", config.worker)
    logger.debug("criteria from config: %s", [entry.code for entry in config.criteria])
    logger.debug("call types from config: %s", [entry.code for entry in config.call_types])


if __name__ == "__main__":
    sys.exit(main())
