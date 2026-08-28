import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config import LoggingConfig
from src.constants import (
    LOG_APPLICATION_LOGGERS,
    LOG_BACKUP_COUNT,
    LOG_FILE_ENV_VAR,
    LOG_FILE_TEMPLATE,
    LOG_FILE_TIME_FORMAT,
    LOG_FORMAT,
    LOG_LATEST_NAME,
    LOG_MAX_BYTES,
)


def new_log_file(directory: Path) -> Path:
    timestamp = datetime.now().strftime(LOG_FILE_TIME_FORMAT)
    return directory / LOG_FILE_TEMPLATE.format(timestamp=timestamp)


def _log_file(directory: Path) -> Path:
    inherited = os.environ.get(LOG_FILE_ENV_VAR)
    return Path(inherited) if inherited else new_log_file(directory)


def _link_latest(directory: Path, target: Path) -> None:
    latest = directory / LOG_LATEST_NAME
    latest.unlink(missing_ok=True)
    try:
        latest.symlink_to(target.name)
    except OSError:
        latest.write_text(target.name, encoding="utf-8")


def setup_logging(config: LoggingConfig) -> None:
    root = logging.getLogger()
    root.setLevel(config.level if config.external_logs else config.external_level)
    root.handlers.clear()
    for name in LOG_APPLICATION_LOGGERS:
        logging.getLogger(name).setLevel(config.level)

    formatter = logging.Formatter(LOG_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    config.dir.mkdir(parents=True, exist_ok=True)
    log_file = _log_file(config.dir)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _link_latest(config.dir, log_file)
