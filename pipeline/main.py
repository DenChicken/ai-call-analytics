import argparse
import logging
import sys
import threading

from src import shutdown
from src.asr import Asr
from src.config import Config, ConfigError, load_config
from src.constants import (
    CALL_TYPES_TABLE,
    CRITERIA_TABLE,
    SHUTDOWN_EXIT_CODE,
    WORKER_THREAD_NAME,
)
from src.database import Database
from src.llm import Llm
from src.logging_setup import setup_logging
from src.worker import Models, run

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

    shutdown.install_handlers()

    database = None
    try:
        database = Database(config.database.dsn, config.worker.count)
        for table, entries in (
            (CRITERIA_TABLE, config.criteria),
            (CALL_TYPES_TABLE, config.call_types),
        ):
            disabled = database.sync_reference(table, entries)
            logger.info("%s synced: %s enabled, %s disabled", table, len(entries), disabled)

        restored = database.reset_interrupted()
        if restored:
            logger.info("restored %s interrupted jobs", restored)

        models = Models(asr=Asr(config.asr), llm=Llm(config.llm))
    except Exception:
        logger.exception("initialization failed")
        if database is not None:
            database.close()
        return 1

    _run_workers(config, database, models)
    database.close()
    stopping = shutdown.is_stopping()
    logger.info("pipeline %s", "stopped on request" if stopping else "finished")
    return SHUTDOWN_EXIT_CODE if stopping else 0


def _log_startup(config: Config) -> None:
    logger.info(
        "pipeline starting: asr=%s llm=%s prompt=%s workers=%s",
        config.asr.repo_id,
        config.llm.repo_id,
        config.prompt.label,
        config.worker.count,
    )
    logger.debug("asr config: %s", config.asr)
    logger.debug("llm config: %s", config.llm)
    logger.debug("worker config: %s", config.worker)
    logger.debug("criteria from config: %s", [entry.code for entry in config.criteria])
    logger.debug("call types from config: %s", [entry.code for entry in config.call_types])


def _run_workers(config: Config, database: Database, models: Models) -> None:
    threads = [
        threading.Thread(
            target=_worker_entry,
            args=(config, database, models),
            name=WORKER_THREAD_NAME.format(number=number),
        )
        for number in range(config.worker.count)
    ]
    logger.info("starting %s workers", len(threads))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    logger.info("all workers stopped")


def _worker_entry(config: Config, database: Database, models: Models) -> None:
    try:
        run(config, database, models)
    except shutdown.ShutdownRequested:
        logger.info("worker stopped")
    except Exception:
        logger.exception("worker crashed")


if __name__ == "__main__":
    sys.exit(main())
