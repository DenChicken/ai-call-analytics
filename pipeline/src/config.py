import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

from src.constants import (
    PROMPT_CRITERIA_PLACEHOLDER,
    PROMPT_MANAGER_PLACEHOLDER,
    PROMPT_TRANSCRIPT_PLACEHOLDER,
)

TOKEN_BLOCK = 16
JSON_OVERHEAD_TOKENS = 64
LIST_FIELD_COUNT = 3
PROMPT_PLACEHOLDERS = (
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
class TranscriptConfig:
    language: str
    beam_size: int
    condition_on_previous_text: bool
    hallucination_silence_threshold: float
    word_timestamps: bool
    vad_filter: bool
    min_silence_duration_ms: int
    speech_pad_ms: int
    break_silence_ms: int


@dataclass(frozen=True)
class AsrConfig:
    repo_id: str
    local_dir: Path
    device: str
    compute_type: str
    unload_after: bool
    transcript: TranscriptConfig


@dataclass(frozen=True)
class OutputConfig:
    list_items: int
    tokens_per_item: int
    summary_tokens: int

    @property
    def max_new_tokens(self) -> int:
        total = (
            self.summary_tokens
            + LIST_FIELD_COUNT * self.list_items * self.tokens_per_item
            + JSON_OVERHEAD_TOKENS
        )
        return math.ceil(total / TOKEN_BLOCK) * TOKEN_BLOCK


@dataclass(frozen=True)
class LlmConfig:
    repo_id: str
    local_dir: Path
    device: str
    torch_dtype: str
    load_in_4bit: bool
    max_input_tokens: int
    temperature: float
    top_p: float
    top_k: int
    unload_after: bool
    output: OutputConfig


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
    llm: LlmConfig
    prompt: PromptConfig
    logging: LoggingConfig
    criteria: list[Criterion]


def _section(raw: dict, name: str, parent: str = "") -> dict:
    if name not in raw:
        raise ConfigError(f"missing required section [{parent}{name}]")
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


def _load_asr(raw: dict) -> AsrConfig:
    section = _section(raw, "asr")
    transcript_raw = _section(section, "transcript", "asr.")
    where = "asr.transcript"
    return AsrConfig(
        repo_id=_require(section, "repo_id", "asr"),
        local_dir=Path(_require(section, "local_dir", "asr")).resolve(),
        device=_require(section, "device", "asr"),
        compute_type=_require(section, "compute_type", "asr"),
        unload_after=_require(section, "unload_after", "asr"),
        transcript=TranscriptConfig(
            language=_require(transcript_raw, "language", where),
            beam_size=_require(transcript_raw, "beam_size", where),
            condition_on_previous_text=_require(
                transcript_raw, "condition_on_previous_text", where
            ),
            hallucination_silence_threshold=_require(
                transcript_raw, "hallucination_silence_threshold", where
            ),
            word_timestamps=_require(transcript_raw, "word_timestamps", where),
            vad_filter=_require(transcript_raw, "vad_filter", where),
            min_silence_duration_ms=_require(transcript_raw, "min_silence_duration_ms", where),
            speech_pad_ms=_require(transcript_raw, "speech_pad_ms", where),
            break_silence_ms=_require(transcript_raw, "break_silence_ms", where),
        ),
    )


def _load_llm(raw: dict) -> LlmConfig:
    section = _section(raw, "llm")
    output_raw = _section(section, "output", "llm.")
    return LlmConfig(
        repo_id=_require(section, "repo_id", "llm"),
        local_dir=Path(_require(section, "local_dir", "llm")).resolve(),
        device=_require(section, "device", "llm"),
        torch_dtype=_require(section, "torch_dtype", "llm"),
        load_in_4bit=_require(section, "load_in_4bit", "llm"),
        max_input_tokens=_require(section, "max_input_tokens", "llm"),
        temperature=_require(section, "temperature", "llm"),
        top_p=_require(section, "top_p", "llm"),
        top_k=_require(section, "top_k", "llm"),
        unload_after=_require(section, "unload_after", "llm"),
        output=OutputConfig(
            list_items=_require(output_raw, "list_items", "llm.output"),
            tokens_per_item=_require(output_raw, "tokens_per_item", "llm.output"),
            summary_tokens=_require(output_raw, "summary_tokens", "llm.output"),
        ),
    )


def _load_prompt(raw: dict) -> PromptConfig:
    section = _section(raw, "prompt")
    user_path = _require(section, "user_file", "prompt")
    user = _read_text_file(user_path, "prompt")
    for placeholder in PROMPT_PLACEHOLDERS:
        if "{" + placeholder + "}" not in user:
            raise ConfigError(
                f"user prompt {user_path} must contain the {{{placeholder}}} placeholder"
            )
    return PromptConfig(
        label=_require(section, "label", "prompt"),
        system=_read_text_file(_require(section, "system_file", "prompt"), "prompt"),
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
    huggingface_raw = _section(raw, "huggingface")
    logging_raw = _section(raw, "logging")

    read_secret_file(_require(huggingface_raw, "token_file", "huggingface"))

    database = DatabaseConfig(dsn=read_secret_file(_require(database_raw, "dsn_file", "database")))

    storage = StorageConfig(done_dir=Path(_require(storage_raw, "done_dir", "storage")).resolve())

    worker = WorkerConfig(
        count=_require(worker_raw, "count", "worker"),
        poll_interval_seconds=_require(worker_raw, "poll_interval_seconds", "worker"),
        max_attempts=_require(worker_raw, "max_attempts", "worker"),
    )

    asr = _load_asr(raw)
    llm = _load_llm(raw)

    logging_config = LoggingConfig(
        level=_require(logging_raw, "level", "logging"),
        dir=Path(_require(logging_raw, "dir", "logging")),
        external_logs=_require(logging_raw, "external_logs", "logging"),
        external_level=_require(logging_raw, "external_level", "logging"),
    )

    unloading = [name for name, model in (("asr", asr), ("llm", llm)) if model.unload_after]
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
        llm=llm,
        prompt=_load_prompt(raw),
        logging=logging_config,
        criteria=_load_criteria(_require(criteria_raw, "file", "criteria")),
    )
