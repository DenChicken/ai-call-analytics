import argparse
import logging
import signal
import sys
import threading

from src.config import ConfigError, load_config
from src.database import Database
from src.logging_setup import setup_logging
from src.models.qwen_analyzer import QwenAnalyzer
from src.models.whisperx_transcriber import WhisperxTranscriber
from src.storage import prepare_dirs
from src.worker import run_worker

WORKER_NAME_TEMPLATE = "w{index}"

logger = logging.getLogger(__name__)

stop = threading.Event()


def handle_signal(signum, frame) -> None:
    logger.info("received signal %s, finishing current work", signum)
    stop.set()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze call recordings with ASR and an LLM")
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
    prepare_dirs(config.storage)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    registry = Database(config.database.dsn)
    revived = registry.sync_criteria(config.llm.criteria)
    for code in revived:
        logger.warning("criterion %s was inactive and is active again", code)
    released = registry.release_stale(
        config.worker.claim_timeout_seconds, config.worker.max_attempts
    )
    if released:
        logger.info("released %s stale recordings", released)
    registry.close()

    resources = []
    threads = []
    try:
        for index in range(config.worker.count):
            database = Database(config.database.dsn)
            transcriber = WhisperxTranscriber(config.asr)
            analyzer = QwenAnalyzer(config.llm)
            resources.append((database, transcriber, analyzer))
            thread = threading.Thread(
                target=run_worker,
                args=(
                    WORKER_NAME_TEMPLATE.format(index=index),
                    config,
                    database,
                    transcriber,
                    analyzer,
                    stop,
                ),
                daemon=True,
            )
            thread.start()
            threads.append(thread)

        while any(thread.is_alive() for thread in threads):
            stop.wait(config.worker.poll_interval_seconds)
    finally:
        stop.set()
        for thread in threads:
            thread.join()
        for database, transcriber, analyzer in resources:
            database.close()
            transcriber.close()
            analyzer.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
