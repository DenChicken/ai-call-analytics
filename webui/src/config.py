import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class DatabaseConfig:
    dsn: str


@dataclass(frozen=True)
class StorageConfig:
    root_dir: Path


@dataclass(frozen=True)
class ServerConfig:
    host: str
    scheme: str
    frontend_port: int
    backend_port: int

    @property
    def api_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.backend_port}"

    @property
    def frontend_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.frontend_port}"


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
class Config:
    database: DatabaseConfig
    storage: StorageConfig
    server: ServerConfig
    session: SessionConfig
    display: DisplayConfig
    logging: LoggingConfig


def _section(raw: dict, name: str) -> dict:
    if name not in raw:
        raise ConfigError(f"missing required section [{name}]")
    return raw[name]


def _require(section: dict, key: str, where: str):
    if key not in section:
        raise ConfigError(f"missing required key '{key}' in [{where}]")
    return section[key]


def resolve_path(base_dir: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


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

    base_dir = path.resolve().parent

    database_raw = _section(raw, "database")
    storage_raw = _section(raw, "storage")
    server_raw = _section(raw, "server")
    session_raw = _section(raw, "session")
    display_raw = _section(raw, "display")
    logging_raw = _section(raw, "logging")

    return Config(
        database=DatabaseConfig(
            dsn=read_secret_file(
                resolve_path(base_dir, _require(database_raw, "dsn_file", "database"))
            )
        ),
        storage=StorageConfig(
            root_dir=resolve_path(base_dir, _require(storage_raw, "root_dir", "storage")),
        ),
        server=ServerConfig(
            host=_require(server_raw, "host", "server"),
            scheme=_require(server_raw, "scheme", "server"),
            frontend_port=_require(server_raw, "frontend_port", "server"),
            backend_port=_require(server_raw, "backend_port", "server"),
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
            level=_require(logging_raw, "level", "logging"),
            dir=resolve_path(base_dir, _require(logging_raw, "dir", "logging")),
            external_logs=_require(logging_raw, "external_logs", "logging"),
            external_level=_require(logging_raw, "external_level", "logging"),
        ),
    )
