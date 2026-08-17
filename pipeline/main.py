import argparse
import logging
import sys
import threading

from src import shutdown
from src.asr import Asr
from src.config import Config, ConfigError, load_config
from src.constants import SHUTDOWN_EXIT_CODE, WORKER_THREAD_NAME
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
    config.storage.done_dir.mkdir(parents=True, exist_ok=True)

    shutdown.install_handlers()

    database = Database(config.database.dsn, config.worker.count)
    try:
        disabled = database.sync_criteria(config.criteria)
        logger.info("criteria synced: %s enabled, %s disabled", len(config.criteria), disabled)

        restored = database.reset_interrupted()
        if restored:
            logger.info("restored %s interrupted jobs", restored)

        roles_llm = Llm(config.roles_llm)
        shared = roles_llm if roles_llm.shares_weights_with(config.analysis_llm) else None
        analysis_llm = Llm(config.analysis_llm, loaded=shared)
        models = Models(asr=Asr(config.asr), roles_llm=roles_llm, analysis_llm=analysis_llm)
    except Exception:
        logger.exception("initialization failed")
        database.close()
        return 1

    _run_workers(config, database, models)
    database.close()
    return SHUTDOWN_EXIT_CODE if shutdown.is_stopping() else 0


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
