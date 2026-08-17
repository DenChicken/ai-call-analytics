import tomllib
from dataclasses import dataclass
from pathlib import Path

from src.constants import PROMPT_CRITERIA_PLACEHOLDER, PROMPT_TRANSCRIPT_PLACEHOLDER


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class DatabaseConfig:
    dsn: str


@dataclass(frozen=True)
class StorageConfig:
    done_dir: Path


@dataclass(frozen=True)
class WorkerConfig:
    count: int
    poll_interval_seconds: float
    max_attempts: int


@dataclass(frozen=True)
class AsrConfig:
    repo_id: str
    local_dir: Path
    device: str
    compute_type: str
    language: str
    beam_size: int
    vad_filter: bool


@dataclass(frozen=True)
class DiarizationConfig:
    repo_id: str
    local_dir: Path
    device: str
    max_speakers: int


@dataclass(frozen=True)
class LlmConfig:
    repo_id: str
    local_dir: Path
    device: str
    torch_dtype: str
    load_in_4bit: bool
    max_input_tokens: int
    max_new_tokens: int
    temperature: float


@dataclass(frozen=True)
class PromptConfig:
    label: str
    system: str
    user: str


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    dir: Path
    external_logs: bool
    external_level: str


@dataclass(frozen=True)
class Criterion:
    code: str
    label: str
    description: str


@dataclass(frozen=True)
class Config:
    database: DatabaseConfig
    storage: StorageConfig
    worker: WorkerConfig
    asr: AsrConfig
    diarization: DiarizationConfig
    llm: LlmConfig
    prompt: PromptConfig
    logging: LoggingConfig
    criteria: list[Criterion]


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


def _read_text_file(path: str | Path, where: str) -> str:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"file not found: {path} (referenced by [{where}])")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ConfigError(f"file is empty: {path} (referenced by [{where}])")
    return text


def _read_user_prompt(path: str | Path) -> str:
    text = _read_text_file(path, "prompt")
    for placeholder in (PROMPT_CRITERIA_PLACEHOLDER, PROMPT_TRANSCRIPT_PLACEHOLDER):
        if "{" + placeholder + "}" not in text:
            raise ConfigError(f"user prompt {path} must contain the {{{placeholder}}} placeholder")
    return text


def _load_criteria(path: str | Path) -> list[Criterion]:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"criteria file not found: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    entries = raw.get("criterion", [])
    if not entries:
        raise ConfigError(f"at least one [[criterion]] must be defined in {path}")

    criteria = []
    seen = set()
    for entry in entries:
        code = _require(entry, "code", "criterion")
        if code in seen:
            raise ConfigError(f"duplicate criterion code '{code}' in {path}")
        seen.add(code)
        criteria.append(
            Criterion(
                code=code,
                label=_require(entry, "label", "criterion"),
                description=_require(entry, "description", "criterion"),
            )
        )
    return criteria


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    database_raw = _section(raw, "database")
    storage_raw = _section(raw, "storage")
    worker_raw = _section(raw, "worker")
    criteria_raw = _section(raw, "criteria")
    asr_raw = _section(raw, "asr")
    diarization_raw = _section(raw, "diarization")
    llm_raw = _section(raw, "llm")
    prompt_raw = _section(raw, "prompt")
    logging_raw = _section(raw, "logging")

    database = DatabaseConfig(dsn=read_secret_file(_require(database_raw, "dsn_file", "database")))

    storage = StorageConfig(done_dir=Path(_require(storage_raw, "done_dir", "storage")).resolve())

    worker = WorkerConfig(
        count=_require(worker_raw, "count", "worker"),
        poll_interval_seconds=_require(worker_raw, "poll_interval_seconds", "worker"),
        max_attempts=_require(worker_raw, "max_attempts", "worker"),
    )

    asr = AsrConfig(
        repo_id=_require(asr_raw, "repo_id", "asr"),
        local_dir=Path(_require(asr_raw, "local_dir", "asr")).resolve(),
        device=_require(asr_raw, "device", "asr"),
        compute_type=_require(asr_raw, "compute_type", "asr"),
        language=_require(asr_raw, "language", "asr"),
        beam_size=_require(asr_raw, "beam_size", "asr"),
        vad_filter=_require(asr_raw, "vad_filter", "asr"),
    )

    diarization = DiarizationConfig(
        repo_id=_require(diarization_raw, "repo_id", "diarization"),
        local_dir=Path(_require(diarization_raw, "local_dir", "diarization")).resolve(),
        device=_require(diarization_raw, "device", "diarization"),
        max_speakers=_require(diarization_raw, "max_speakers", "diarization"),
    )

    llm = LlmConfig(
        repo_id=_require(llm_raw, "repo_id", "llm"),
        local_dir=Path(_require(llm_raw, "local_dir", "llm")).resolve(),
        device=_require(llm_raw, "device", "llm"),
        torch_dtype=_require(llm_raw, "torch_dtype", "llm"),
        load_in_4bit=_require(llm_raw, "load_in_4bit", "llm"),
        max_input_tokens=_require(llm_raw, "max_input_tokens", "llm"),
        max_new_tokens=_require(llm_raw, "max_new_tokens", "llm"),
        temperature=_require(llm_raw, "temperature", "llm"),
    )

    prompt = PromptConfig(
        label=_require(prompt_raw, "label", "prompt"),
        system=_read_text_file(_require(prompt_raw, "system_file", "prompt"), "prompt"),
        user=_read_user_prompt(_require(prompt_raw, "user_file", "prompt")),
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
        worker=worker,
        asr=asr,
        diarization=diarization,
        llm=llm,
        prompt=prompt,
        logging=logging_config,
        criteria=_load_criteria(_require(criteria_raw, "file", "criteria")),
    )
