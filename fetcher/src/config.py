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
    pending_dir: Path
    temp_dir: Path


@dataclass(frozen=True)
class FetchConfig:
    interval_seconds: int
    min_call_duration_seconds: int
    max_call_duration_seconds: int
    initial_lookback_days: int
    max_records_per_cycle: int
    download_cooldown_seconds: float


@dataclass(frozen=True)
class NetworkConfig:
    connect_timeout: float
    read_timeout: float
    download_timeout: float
    max_retries: int
    backoff_base_seconds: float
    backoff_max_seconds: float
    requests_per_second: float


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    dir: Path
    external_logs: bool
    external_level: str


@dataclass(frozen=True)
class SourceConfig:
    name: str
    kind: str
    options: dict


@dataclass(frozen=True)
class Config:
    database: DatabaseConfig
    storage: StorageConfig
    fetch: FetchConfig
    network: NetworkConfig
    logging: LoggingConfig
    sources: list[SourceConfig]


def _section(raw: dict, name: str) -> dict:
    if name not in raw:
        raise ConfigError(f"missing required section [{name}]")
    return raw[name]


def _require(section: dict, key: str, where: str):
    if key not in section:
        raise ConfigError(f"missing required key '{key}' in [{where}]")
    return section[key]


def require_option(source_config: SourceConfig, key: str):
    if key not in source_config.options:
        raise ConfigError(f"missing required key '{key}' in [[source]] '{source_config.name}'")
    return source_config.options[key]


def read_secret_file(path: str | Path) -> str:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"secret file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        value = handle.readline().strip()
    if not value:
        raise ConfigError(f"secret file is empty: {path}")
    return value


def _load_sources(raw: list) -> list[SourceConfig]:
    if not raw:
        raise ConfigError("at least one [[source]] must be defined")

    sources = []
    seen = set()
    for entry in raw:
        name = _require(entry, "name", "source")
        kind = _require(entry, "kind", "source")
        if name in seen:
            raise ConfigError(f"duplicate source name '{name}'")
        seen.add(name)
        options = {k: v for k, v in entry.items() if k not in ("name", "kind")}
        sources.append(SourceConfig(name=name, kind=kind, options=options))
    return sources


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    database_raw = _section(raw, "database")
    storage_raw = _section(raw, "storage")
    fetch_raw = _section(raw, "fetch")
    network_raw = _section(raw, "network")
    logging_raw = _section(raw, "logging")

    database = DatabaseConfig(dsn=read_secret_file(_require(database_raw, "dsn_file", "database")))

    storage = StorageConfig(
        pending_dir=Path(_require(storage_raw, "pending_dir", "storage")).resolve(),
        temp_dir=Path(_require(storage_raw, "temp_dir", "storage")).resolve(),
    )

    fetch = FetchConfig(
        interval_seconds=_require(fetch_raw, "interval_seconds", "fetch"),
        min_call_duration_seconds=_require(fetch_raw, "min_call_duration_seconds", "fetch"),
        max_call_duration_seconds=_require(fetch_raw, "max_call_duration_seconds", "fetch"),
        initial_lookback_days=_require(fetch_raw, "initial_lookback_days", "fetch"),
        max_records_per_cycle=_require(fetch_raw, "max_records_per_cycle", "fetch"),
        download_cooldown_seconds=_require(fetch_raw, "download_cooldown_seconds", "fetch"),
    )

    if fetch.max_call_duration_seconds <= fetch.min_call_duration_seconds:
        raise ConfigError(
            f"max_call_duration_seconds ({fetch.max_call_duration_seconds}) must be greater "
            f"than min_call_duration_seconds ({fetch.min_call_duration_seconds}) in [fetch]"
        )

    network = NetworkConfig(
        connect_timeout=_require(network_raw, "connect_timeout", "network"),
        read_timeout=_require(network_raw, "read_timeout", "network"),
        download_timeout=_require(network_raw, "download_timeout", "network"),
        max_retries=_require(network_raw, "max_retries", "network"),
        backoff_base_seconds=_require(network_raw, "backoff_base_seconds", "network"),
        backoff_max_seconds=_require(network_raw, "backoff_max_seconds", "network"),
        requests_per_second=_require(network_raw, "requests_per_second", "network"),
    )

    logging_config = LoggingConfig(
        level=_require(logging_raw, "level", "logging"),
        dir=Path(_require(logging_raw, "dir", "logging")),
        external_logs=_require(logging_raw, "external_logs", "logging"),
        external_level=_require(logging_raw, "external_level", "logging"),
    )

    return Config(
        database=database,
        storage=storage,
        fetch=fetch,
        network=network,
        logging=logging_config,
        sources=_load_sources(raw.get("source", [])),
    )
