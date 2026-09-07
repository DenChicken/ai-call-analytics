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
    CONFIG_EXIT_CODE,
    CRITERIA_TABLE,
    SHUTDOWN_EXIT_CODE,
    UNRECOVERABLE_EXIT_CODE,
)
from src.db import Database
from src.errors import FatalError
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
        return CONFIG_EXIT_CODE

    setup_logging(config.logging, config.logs_dir)
    _log_startup(config)
    shutdown.install_handlers()

    try:
        license = load(config.license_file)
        check(license)
        logger.info("license valid until %s", license.expires)

        with Database(config) as database:
            database.sync_references(
                {CRITERIA_TABLE: config.criteria, CALL_TYPES_TABLE: config.call_types}
            )
            asr = Asr(config.asr, config.asr_dir)
            llm = Llm(config.llm, config.llm_dir)
            config.done_dir.mkdir(parents=True, exist_ok=True)
            run(config, database, asr, llm, license)
    except LicenseError as error:
        return _stop(f"license error: {error}", LICENSE_EXIT_CODE)
    except shutdown.LicenseExpired as error:
        return _stop(f"license expired: {error}", LICENSE_EXIT_CODE)
    except shutdown.ShutdownRequested:
        logger.info("pipeline stopped on request")
        return SHUTDOWN_EXIT_CODE
    except FatalError as error:
        return _stop(f"pipeline stopping, the queue is untouched: {error}", UNRECOVERABLE_EXIT_CODE)
    except Exception:
        logger.exception("pipeline crashed")
        return UNRECOVERABLE_EXIT_CODE

    logger.info("pipeline stopped")
    return SHUTDOWN_EXIT_CODE


def _stop(message: str, code: int) -> int:
    print(message, file=sys.stderr)
    logger.error(message)
    return code


def _log_startup(config: Config) -> None:
    logger.info(
        "pipeline starting: asr=%s on %s, llm=%s on %s, prompt=%s",
        config.asr.repo_id,
        config.asr.device,
        config.llm.repo_id,
        config.llm.device,
        config.prompt_label,
    )
    logger.debug("asr: %s", config.asr)
    logger.debug("llm: %s", config.llm)
    logger.debug("worker: %s", config.worker)
    logger.debug("criteria: %s", [entry.code for entry in config.criteria])
    logger.debug("call types: %s", [entry.code for entry in config.call_types])


if __name__ == "__main__":
    sys.exit(main())
