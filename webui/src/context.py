import atexit
import os
from pathlib import Path

from src.audio import AudioStore
from src.config import Config, ConfigError, load_config
from src.constants import CONFIG_ENV_VAR
from src.database import Database
from src.logging_setup import setup_logging

_config: Config | None = None
_database: Database | None = None
_audio: AudioStore | None = None


def config() -> Config:
    global _config
    if _config is None:
        path = os.environ.get(CONFIG_ENV_VAR)
        if not path:
            raise ConfigError(
                "config path is not known: start the web interface with "
                "'python main.py -c <config>' instead of running reflex directly"
            )
        _config = load_config(Path(path))
        setup_logging(_config.logging)
    return _config


def database() -> Database:
    global _database
    if _database is None:
        _database = Database(config().database.dsn)
        atexit.register(_close_database)
    return _database


def _close_database() -> None:
    global _database
    if _database is not None:
        _database.close()
        _database = None


def audio() -> AudioStore:
    global _audio
    if _audio is None:
        _audio = AudioStore(config().storage)
    return _audio
