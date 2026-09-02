import atexit
import logging
import os
from pathlib import Path

from licensing.license import License, LicenseError
from licensing.verify_runtime import is_expired, load

from src.audio import AudioStore
from src.config import Config, ConfigError, load_config
from src.constants import CONFIG_ENV_VAR, LICENSE_UNAVAILABLE_MESSAGE
from src.database import Database
from src.logging_setup import setup_logging

logger = logging.getLogger(__name__)

_config: Config | None = None
_database: Database | None = None
_audio: AudioStore | None = None
_license: License | None = None


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


def license() -> License:
    global _license
    if _license is None:
        _license = load(config().license.file)
    return _license


def _reload_license() -> License:
    global _license
    _license = load(config().license.file)
    return _license


def license_expired() -> bool:
    try:
        if not is_expired(license()):
            return False
        reloaded = _reload_license()
        if not is_expired(reloaded):
            logger.info("license replaced, valid until %s", reloaded.expires)
            return False
    except LicenseError:
        logger.exception(LICENSE_UNAVAILABLE_MESSAGE)
        return True
    return True


def license_contact() -> str:
    try:
        return license().contact
    except LicenseError:
        return ""
