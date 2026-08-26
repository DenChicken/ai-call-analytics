import logging
from pathlib import Path

from src.config import StorageConfig

logger = logging.getLogger(__name__)


class AudioStore:
    def __init__(self, config: StorageConfig):
        self._data_dir = config.data_dir

    def locate(self, audio_path: str | None) -> Path | None:
        if not audio_path:
            return None

        path = self._data_dir / audio_path
        if path.is_file():
            return path

        logger.debug("audio file not found: %s", path)
        return None
