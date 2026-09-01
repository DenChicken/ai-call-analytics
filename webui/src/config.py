import tomllib
from dataclasses import dataclass
from pathlib import Path

from src.constants import (
    LOG_LEVELS,
    LOG_MODULE_DIR,
    SAME_DOMAIN_HOST,
    SAME_DOMAIN_SCHEME,
)

PATHS_SECTION = "paths"
LOGGING_SECTION = "logging"
LICENSE_SECTION = "license"
DATA_DIR_KEY = "data_dir"
SECRETS_DIR_KEY = "secrets_dir"
LOGS_DIR_KEY = "logs_dir"
LICENSE_FILE_KEY = "file"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class DatabaseConfig:
    dsn: str


@dataclass(frozen=True)
class StorageConfig:
    data_dir: Path


@dataclass(frozen=True)
class ServerConfig:
    frontend_port: int
    backend_port: int
    backend_path: str

    @property
    def api_url(self) -> str:
        return f"{SAME_DOMAIN_SCHEME}://{SAME_DOMAIN_HOST}:{self.backend_port}"

    @property
    def local_url(self) -> str:
        return f"{SAME_DOMAIN_SCHEME}://{SAME_DOMAIN_HOST}:{self.frontend_port}"


@dataclass(frozen=True)
class SessionConfig:
    max_age_seconds: int
    cookie_secure: bool


@dataclass(frozen=True)
class DisplayConfig:
    timezone: str
    refresh_seconds: int
    page_size: int
    queue_size: int


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    dir: Path
    external_logs: bool
    external_level: str


@dataclass(frozen=True)
class LicenseConfig:
    file: Path


@dataclass(frozen=True)
class Config:
    database: DatabaseConfig
    storage: StorageConfig
    server: ServerConfig
    session: SessionConfig
    display: DisplayConfig
    logging: LoggingConfig
    license: LicenseConfig


def _section(raw: dict, name: str) -> dict:
    if name not in raw:
        raise ConfigError(f"missing required section [{name}]")
    return raw[name]


def _require(section: dict, key: str, where: str):
    if key not in section:
        raise ConfigError(f"missing required key '{key}' in [{where}]")
    return section[key]


def _require_level(section: dict, key: str) -> str:
    value = str(_require(section, key, LOGGING_SECTION)).upper()
    if value not in LOG_LEVELS:
        raise ConfigError(
            f"'{key}' in [{LOGGING_SECTION}] is {value}, expected one of: {', '.join(LOG_LEVELS)}"
        )
    return value


def resolve_anchor(raw: dict, key: str) -> Path:
    value = Path(_require(raw, key, PATHS_SECTION))
    if not value.is_absolute():
        raise ConfigError(
            f"'{key}' in [{PATHS_SECTION}] must be an absolute path, got {value}: "
            "anchors are mount points and cannot depend on where the config file sits"
        )
    return value.resolve()


def resolve_inside(anchor: Path, value: str | Path, key: str, where: str) -> Path:
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (anchor / path).resolve()
    if not path.is_relative_to(anchor):
        raise ConfigError(
            f"'{key}' in [{where}] resolves to {path}, which is outside {anchor}: "
            "it must stay inside its anchor directory"
        )
    return path


def read_secret_file(path: str | Path) -> str:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"secret file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        value = handle.readline().strip()
    if not value:
        raise ConfigError(f"secret file is empty: {path}")
    return value


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    paths_raw = _section(raw, PATHS_SECTION)
    data_dir = resolve_anchor(paths_raw, DATA_DIR_KEY)
    secrets_dir = resolve_anchor(paths_raw, SECRETS_DIR_KEY)
    logs_dir = resolve_anchor(paths_raw, LOGS_DIR_KEY)

    database_raw = _section(raw, "database")
    server_raw = _section(raw, "server")
    session_raw = _section(raw, "session")
    display_raw = _section(raw, "display")
    logging_raw = _section(raw, "logging")
    license_raw = _section(raw, LICENSE_SECTION)

    return Config(
        database=DatabaseConfig(
            dsn=read_secret_file(
                resolve_inside(
                    secrets_dir,
                    _require(database_raw, "dsn_file", "database"),
                    "dsn_file",
                    "database",
                )
            )
        ),
        storage=StorageConfig(data_dir=data_dir),
        server=ServerConfig(
            frontend_port=_require(server_raw, "frontend_port", "server"),
            backend_port=_require(server_raw, "backend_port", "server"),
            backend_path=_require(server_raw, "backend_path", "server"),
        ),
        session=SessionConfig(
            max_age_seconds=_require(session_raw, "max_age_seconds", "session"),
            cookie_secure=_require(session_raw, "cookie_secure", "session"),
        ),
        display=DisplayConfig(
            timezone=_require(display_raw, "timezone", "display"),
            refresh_seconds=_require(display_raw, "refresh_seconds", "display"),
            page_size=_require(display_raw, "page_size", "display"),
            queue_size=_require(display_raw, "queue_size", "display"),
        ),
        logging=LoggingConfig(
            level=_require_level(logging_raw, "level"),
            dir=logs_dir / LOG_MODULE_DIR,
            external_logs=_require(logging_raw, "external_logs", "logging"),
            external_level=_require_level(logging_raw, "external_level"),
        ),
        license=LicenseConfig(
            file=resolve_inside(
                secrets_dir,
                _require(license_raw, LICENSE_FILE_KEY, LICENSE_SECTION),
                LICENSE_FILE_KEY,
                LICENSE_SECTION,
            )
        ),
    )
