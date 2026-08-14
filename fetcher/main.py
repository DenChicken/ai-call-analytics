import argparse
import logging
import signal
import sys
import threading

from src.config import ConfigError, load_config
from src.database import Database
from src.fetch import run_once
from src.logging_setup import setup_logging
from src.sources import create_source

logger = logging.getLogger(__name__)

stop = threading.Event()


def handle_signal(signum, frame) -> None:
    logger.info("received signal %s, finishing current cycle", signum)
    stop.set()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch call recordings from CRM systems")
    parser.add_argument("-c", "--config", required=True, help="path to TOML config")
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

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    database = Database(config.database.dsn)
    try:
        while not stop.is_set():
            for source in sources:
                try:
                    run_once(config, database, source)
                except Exception:
                    logger.exception("cycle failed for source %s", source.name)
            if args.once:
                break
            stop.wait(config.fetch.interval_seconds)
    finally:
        for source in sources:
            source.close()
        database.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
