from datetime import datetime, timezone
from pathlib import Path

from src.config import StorageConfig
from src.constants import DONE_DAY_FORMAT, DONE_MONTH_FORMAT


def prepare_dirs(config: StorageConfig) -> None:
    for directory in (config.pending_dir, config.processing_dir, config.done_dir):
        directory.mkdir(parents=True, exist_ok=True)


def move_to_processing(config: StorageConfig, source: Path) -> Path:
    target = config.processing_dir / source.name
    if not source.is_file():
        if target.is_file():
            return target
        raise FileNotFoundError(f"audio file not found: {source}")
    source.replace(target)
    return target


def move_to_done(config: StorageConfig, source: Path, started_at: datetime) -> Path:
    moment = started_at.astimezone(timezone.utc)
    directory = config.done_dir / moment.strftime(DONE_MONTH_FORMAT) / moment.strftime(DONE_DAY_FORMAT)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / source.name
    source.replace(target)
    return target


def move_back_to_pending(config: StorageConfig, source: Path) -> Path:
    target = config.pending_dir / source.name
    if source.is_file():
        source.replace(target)
    return target
