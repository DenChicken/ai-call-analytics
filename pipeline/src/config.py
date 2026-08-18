import tomllib
from dataclasses import dataclass
from pathlib import Path

from src.constants import (
    PROMPT_CRITERIA_PLACEHOLDER,
    PROMPT_MANAGER_PLACEHOLDER,
    PROMPT_TRANSCRIPT_PLACEHOLDER,
)


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
    min_silence_duration_ms: int
    unload_after: bool


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
    top_p: float
    top_k: int
    unload_after: bool


@dataclass(frozen=True)
class PromptConfig:
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
    roles_llm: LlmConfig
    analysis_llm: LlmConfig
    prompt_label: str
    roles_prompt: PromptConfig
    analysis_prompt: PromptConfig
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


def _load_llm(raw: dict, name: str) -> LlmConfig:
    section = _section(raw, name)
    return LlmConfig(
        repo_id=_require(section, "repo_id", name),
        local_dir=Path(_require(section, "local_dir", name)).resolve(),
        device=_require(section, "device", name),
        torch_dtype=_require(section, "torch_dtype", name),
        load_in_4bit=_require(section, "load_in_4bit", name),
        max_input_tokens=_require(section, "max_input_tokens", name),
        max_new_tokens=_require(section, "max_new_tokens", name),
        temperature=_require(section, "temperature", name),
        top_p=_require(section, "top_p", name),
        top_k=_require(section, "top_k", name),
        unload_after=_require(section, "unload_after", name),
    )


def _load_prompt(section: dict, name: str, placeholders: tuple[str, ...]) -> PromptConfig:
    user_path = _require(section, f"{name}_user_file", "prompt")
    user = _read_text_file(user_path, "prompt")
    for placeholder in placeholders:
        if "{" + placeholder + "}" not in user:
            raise ConfigError(
                f"user prompt {user_path} must contain the {{{placeholder}}} placeholder"
            )
    return PromptConfig(
        system=_read_text_file(_require(section, f"{name}_system_file", "prompt"), "prompt"),
        user=user,
    )


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
    models_raw = _section(raw, "models")
    asr_raw = _section(raw, "asr")
    prompt_raw = _section(raw, "prompt")
    logging_raw = _section(raw, "logging")

    read_secret_file(_require(models_raw, "hf_token_file", "models"))

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
        min_silence_duration_ms=_require(asr_raw, "min_silence_duration_ms", "asr"),
        unload_after=_require(asr_raw, "unload_after", "asr"),
    )

    roles_prompt = _load_prompt(
        prompt_raw, "roles", (PROMPT_MANAGER_PLACEHOLDER, PROMPT_TRANSCRIPT_PLACEHOLDER)
    )
    analysis_prompt = _load_prompt(
        prompt_raw, "analysis", (PROMPT_CRITERIA_PLACEHOLDER, PROMPT_TRANSCRIPT_PLACEHOLDER)
    )

    logging_config = LoggingConfig(
        level=_require(logging_raw, "level", "logging"),
        dir=Path(_require(logging_raw, "dir", "logging")),
        external_logs=_require(logging_raw, "external_logs", "logging"),
        external_level=_require(logging_raw, "external_level", "logging"),
    )

    roles_llm = _load_llm(raw, "roles_llm")
    analysis_llm = _load_llm(raw, "analysis_llm")

    models = {"asr": asr, "roles_llm": roles_llm, "analysis_llm": analysis_llm}
    unloading = [name for name, model in models.items() if model.unload_after]
    if worker.count > 1 and unloading:
        raise ConfigError(
            f"unload_after is set in {', '.join(unloading)} but [worker] count is "
            f"{worker.count}: unloading a model shared by several workers would drop it "
            "while another worker is still using it, set count = 1 or unload_after = false"
        )

    return Config(
        database=database,
        storage=storage,
        worker=worker,
        asr=asr,
        roles_llm=roles_llm,
        analysis_llm=analysis_llm,
        prompt_label=_require(prompt_raw, "label", "prompt"),
        roles_prompt=roles_prompt,
        analysis_prompt=analysis_prompt,
        logging=logging_config,
        criteria=_load_criteria(_require(criteria_raw, "file", "criteria")),
    )
