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
    processing_dir: Path
    done_dir: Path


@dataclass(frozen=True)
class WorkerConfig:
    count: int
    poll_interval_seconds: int
    claim_timeout_seconds: int
    max_attempts: int


@dataclass(frozen=True)
class AsrConfig:
    model: str
    device: str
    compute_type: str
    language: str
    batch_size: int
    diarize: bool
    min_speakers: int
    max_speakers: int
    hf_token: str | None


@dataclass(frozen=True)
class LlmConfig:
    model: str
    device: str
    max_input_tokens: int
    max_output_tokens: int
    temperature: float
    prompt_version: str
    criteria: tuple


@dataclass(frozen=True)
class Criterion:
    code: str
    title: str
    prompt: str


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    dir: Path


@dataclass(frozen=True)
class Config:
    database: DatabaseConfig
    storage: StorageConfig
    worker: WorkerConfig
    asr: AsrConfig
    llm: LlmConfig
    logging: LoggingConfig


def _section(raw: dict, name: str) -> dict:
    if name not in raw:
        raise ConfigError(f"missing required section [{name}]")
    return raw[name]


def _require(section: dict, key: str, where: str):
    if key not in section:
        raise ConfigError(f"missing required key '{key}' in [{where}]")
    return section[key]


def read_secret_file(path: str | Path) -> str:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"secret file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        value = handle.readline().strip()
    if not value:
        raise ConfigError(f"secret file is empty: {path}")
    return value


def _load_criteria(path: str | Path) -> tuple:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"criteria file not found: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    entries = raw.get("criteria", [])
    if not entries:
        raise ConfigError(f"at least one [[criteria]] must be defined in {path}")

    criteria = []
    seen = set()
    for entry in entries:
        code = _require(entry, "code", "criteria")
        if code in seen:
            raise ConfigError(f"duplicate criterion code '{code}' in {path}")
        seen.add(code)
        criteria.append(
            Criterion(
                code=code,
                title=_require(entry, "title", "criteria"),
                prompt=_require(entry, "prompt", "criteria"),
            )
        )
    return tuple(criteria)


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    database_raw = _section(raw, "database")
    storage_raw = _section(raw, "storage")
    worker_raw = _section(raw, "worker")
    asr_raw = _section(raw, "asr")
    llm_raw = _section(raw, "llm")
    logging_raw = _section(raw, "logging")

    database = DatabaseConfig(dsn=read_secret_file(_require(database_raw, "dsn_file", "database")))

    storage = StorageConfig(
        pending_dir=Path(_require(storage_raw, "pending_dir", "storage")).resolve(),
        processing_dir=Path(_require(storage_raw, "processing_dir", "storage")).resolve(),
        done_dir=Path(_require(storage_raw, "done_dir", "storage")).resolve(),
    )

    worker = WorkerConfig(
        count=_require(worker_raw, "count", "worker"),
        poll_interval_seconds=_require(worker_raw, "poll_interval_seconds", "worker"),
        claim_timeout_seconds=_require(worker_raw, "claim_timeout_seconds", "worker"),
        max_attempts=_require(worker_raw, "max_attempts", "worker"),
    )

    diarize = _require(asr_raw, "diarize", "asr")
    asr = AsrConfig(
        model=_require(asr_raw, "model", "asr"),
        device=_require(asr_raw, "device", "asr"),
        compute_type=_require(asr_raw, "compute_type", "asr"),
        language=_require(asr_raw, "language", "asr"),
        batch_size=_require(asr_raw, "batch_size", "asr"),
        diarize=diarize,
        min_speakers=_require(asr_raw, "min_speakers", "asr"),
        max_speakers=_require(asr_raw, "max_speakers", "asr"),
        hf_token=read_secret_file(_require(asr_raw, "hf_token_file", "asr")) if diarize else None,
    )

    llm = LlmConfig(
        model=_require(llm_raw, "model", "llm"),
        device=_require(llm_raw, "device", "llm"),
        max_input_tokens=_require(llm_raw, "max_input_tokens", "llm"),
        max_output_tokens=_require(llm_raw, "max_output_tokens", "llm"),
        temperature=_require(llm_raw, "temperature", "llm"),
        prompt_version=_require(llm_raw, "prompt_version", "llm"),
        criteria=_load_criteria(_require(llm_raw, "criteria_file", "llm")),
    )

    logging_config = LoggingConfig(
        level=_require(logging_raw, "level", "logging"),
        dir=Path(_require(logging_raw, "dir", "logging")),
    )

    return Config(
        database=database,
        storage=storage,
        worker=worker,
        asr=asr,
        llm=llm,
        logging=logging_config,
    )
