import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from src.constants import (
    GPU_LAYERS_PRESETS,
    KV_CACHE_TYPES,
    LOG_LEVELS,
    LOG_MODULE_DIR,
    PROMPT_CRITERIA_PLACEHOLDER,
    PROMPT_MANAGER_PLACEHOLDER,
    PROMPT_TRANSCRIPT_PLACEHOLDER,
    PROMPT_TYPES_PLACEHOLDER,
)

PROMPT_PLACEHOLDERS = (
    PROMPT_CRITERIA_PLACEHOLDER,
    PROMPT_TYPES_PLACEHOLDER,
    PROMPT_MANAGER_PLACEHOLDER,
    PROMPT_TRANSCRIPT_PLACEHOLDER,
)


class ConfigError(Exception):
    pass


class Section(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Paths(Section):
    data_dir: Path
    models_dir: Path
    secrets_dir: Path
    logs_dir: Path
    configs_dir: Path

    @field_validator("*")
    @classmethod
    def _absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError(
                f"{value} must be an absolute path: anchors are mount points "
                "and cannot depend on where the config file sits"
            )
        return value.resolve()


class Database(Section):
    dsn_file: str
    connect_timeout: float
    max_retries: int
    backoff_base_seconds: float
    backoff_max_seconds: float

    @field_validator("connect_timeout", "max_retries")
    @classmethod
    def _positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError(f"{value} must be positive")
        return value


class License(Section):
    file: str


class Storage(Section):
    done_dir: str


class Worker(Section):
    poll_interval_seconds: float
    max_attempts: int


class Transcript(Section):
    language: str
    beam_size: int
    condition_on_previous_text: bool
    hallucination_silence_threshold: float
    word_timestamps: bool
    vad_filter: bool
    min_silence_duration_ms: int
    speech_pad_ms: int


class Asr(Section):
    repo_id: str
    local_dir: str
    device: str
    compute_type: str
    unload_after: bool
    transcript: Transcript


class Output(Section):
    list_items: int
    max_tokens: int


class Sampling(Section):
    temperature: float
    top_p: float
    top_k: int
    min_p: float
    repeat_penalty: float
    seed: int


class Llm(Section):
    repo_id: str
    model_file: str
    gpu_layers: str
    context_tokens: int
    batch_tokens: int
    threads: int
    flash_attention: bool
    kv_cache_type: str
    offload_kv_cache: bool
    unload_after: bool
    sampling: Sampling
    output: Output

    @field_validator("gpu_layers")
    @classmethod
    def _resolve_layers(cls, value: str) -> int:
        if value in GPU_LAYERS_PRESETS:
            return GPU_LAYERS_PRESETS[value]
        if value.isdigit():
            return int(value)
        raise ValueError(
            f"{value} is not a layer count or one of: {', '.join(GPU_LAYERS_PRESETS)}"
        )

    @field_validator("kv_cache_type")
    @classmethod
    def _known_cache_type(cls, value: str) -> str:
        if value not in KV_CACHE_TYPES:
            raise ValueError(f"{value} is not one of: {', '.join(KV_CACHE_TYPES)}")
        return value

    @model_validator(mode="after")
    def _fits_context(self) -> "Llm":
        if self.output.max_tokens >= self.context_tokens:
            raise ValueError(
                f"max_tokens {self.output.max_tokens} leaves no room in context_tokens "
                f"{self.context_tokens}: the prompt would never fit"
            )
        if self.batch_tokens > self.context_tokens:
            raise ValueError(
                f"batch_tokens {self.batch_tokens} is over context_tokens {self.context_tokens}"
            )
        return self


class Prompt(Section):
    label: str
    system_file: str
    user_file: str


class Logging(Section):
    level: str
    external_logs: bool
    external_level: str

    @field_validator("level", "external_level")
    @classmethod
    def _known_level(cls, value: str) -> str:
        value = value.upper()
        if value not in LOG_LEVELS:
            raise ValueError(f"{value} is not one of: {', '.join(LOG_LEVELS)}")
        return value


class Reference(Section):
    code: str
    label: str
    description: str

    @field_validator("code")
    @classmethod
    def _usable_as_field(cls, value: str) -> str:
        if value.startswith("_"):
            raise ValueError(f"'{value}' cannot start with an underscore")
        if hasattr(BaseModel, value):
            raise ValueError(f"'{value}' is a reserved name, pick another code")
        return value


class Raw(Section):
    paths: Paths
    database: Database
    license: License
    storage: Storage
    worker: Worker
    criteria: dict[str, str]
    types: dict[str, str]
    asr: Asr
    llm: Llm
    prompt: Prompt
    logging: Logging


class Config:
    def __init__(self, raw: Raw, path: Path):
        self.paths = raw.paths
        self.database = raw.database
        self.worker = raw.worker
        self.asr = raw.asr
        self.llm = raw.llm
        self.logging = raw.logging

        self.dsn = _read_secret(_inside(raw.paths.secrets_dir, raw.database.dsn_file))
        self.license_file = _inside(raw.paths.secrets_dir, raw.license.file)
        self.done_dir = _inside(raw.paths.data_dir, raw.storage.done_dir)
        self.asr_dir = _inside(raw.paths.models_dir, raw.asr.local_dir)
        self.llm_file = _inside(raw.paths.models_dir, raw.llm.model_file)
        self.logs_dir = raw.paths.logs_dir / LOG_MODULE_DIR

        self.prompt_label = raw.prompt.label
        self.system_prompt = _read_text(_inside(raw.paths.configs_dir, raw.prompt.system_file))
        self.user_prompt = _read_text(_inside(raw.paths.configs_dir, raw.prompt.user_file))
        for placeholder in PROMPT_PLACEHOLDERS:
            if "{" + placeholder + "}" not in self.user_prompt:
                raise ConfigError(f"user prompt must contain the {{{placeholder}}} placeholder")

        self.criteria = _read_references(
            _inside(raw.paths.configs_dir, raw.criteria["file"]), "criterion"
        )
        self.call_types = _read_references(
            _inside(raw.paths.configs_dir, raw.types["file"]), "type"
        )
        self.path = path


def load_config(path: str | Path) -> Config:
    path = Path(path)
    try:
        raw = Raw(**_read_toml(path))
    except ValidationError as error:
        raise ConfigError(f"{path}: {_describe(error)}") from error
    return Config(raw, path)


def storage_path(data_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(data_dir).as_posix()


def _describe(error: ValidationError) -> str:
    return "; ".join(
        f"[{'.'.join(str(part) for part in item['loc'])}] {item['msg']}"
        for item in error.errors()
    )


def _read_toml(path: Path) -> dict:
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} is not valid TOML: {error}") from error


def _inside(anchor: Path, value: str) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (anchor / path).resolve()
    if not resolved.is_relative_to(anchor):
        raise ConfigError(f"{resolved} is outside {anchor}: it must stay inside its anchor")
    return resolved


def _read_secret(path: Path) -> str:
    if not path.is_file():
        raise ConfigError(f"secret file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        value = handle.readline().strip()
    if not value:
        raise ConfigError(f"secret file is empty: {path}")
    return value


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise ConfigError(f"file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ConfigError(f"file is empty: {path}")
    return text


def _read_references(path: Path, entry_name: str) -> list[Reference]:
    raw = _read_toml(path)
    entries = raw.get(entry_name, [])
    if not entries:
        raise ConfigError(f"at least one [[{entry_name}]] must be defined in {path}")
    try:
        references = [Reference(**entry) for entry in entries]
    except ValidationError as error:
        raise ConfigError(f"{path}: {_describe(error)}") from error

    codes = [entry.code for entry in references]
    duplicates = {code for code in codes if codes.count(code) > 1}
    if duplicates:
        raise ConfigError(f"duplicate {entry_name} codes in {path}: {', '.join(duplicates)}")
    return references
