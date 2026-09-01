import argparse
import logging
import sys

from licensing.constants import LICENSE_EXIT_CODE
from licensing.license import LicenseError
from licensing.verify_runtime import check, load

from src import shutdown
from src.asr import Asr
from src.config import Config, ConfigError, load_config
from src.constants import CALL_TYPES_TABLE, CRITERIA_TABLE, SHUTDOWN_EXIT_CODE
from src.database import Database
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
        database = Database(config.database.dsn)
        for table, entries in (
            (CRITERIA_TABLE, config.criteria),
            (CALL_TYPES_TABLE, config.call_types),
        ):
            disabled = database.sync_reference(table, entries)
            logger.info("%s synced: %s enabled, %s disabled", table, len(entries), disabled)

        asr = Asr(config.asr)
        llm = Llm(config.llm)
    except Exception:
        logger.exception("initialization failed")
        if database is not None:
            database.close()
        return 1

    interrupted = False
    expired = False
    crashed = False
    try:
        run(config, database, asr, llm, license)
    except shutdown.LicenseExpired:
        expired = True
    except shutdown.ShutdownRequested:
        interrupted = True
    except Exception:
        logger.exception("pipeline crashed")
        crashed = True
    finally:
        database.close()

    if crashed:
        return 1
    if expired:
        logger.info("pipeline stopped: license expired")
        return LICENSE_EXIT_CODE
    logger.info("pipeline %s", "stopped on request" if interrupted else "finished")
    return SHUTDOWN_EXIT_CODE if interrupted else 0


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
