import tomllib
from dataclasses import dataclass
from pathlib import Path

from src.constants import (
    PROMPT_CRITERIA_PLACEHOLDER,
    PROMPT_MANAGER_PLACEHOLDER,
    PROMPT_TRANSCRIPT_PLACEHOLDER,
)

REFERENCE_CODE = "code"
REFERENCE_LABEL = "label"
REFERENCE_DESCRIPTION = "description"
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
    root_dir: Path
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
    max_new_tokens: int
    timeout_seconds: float


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
class Reference:
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
    criteria: list[Reference]
    call_types: list[Reference]


def _section(raw: dict, name: str, parent: str = "") -> dict:
    if name not in raw:
        raise ConfigError(f"missing required section [{parent}{name}]")
    return raw[name]


def _require(section: dict, key: str, where: str):
    if key not in section:
        raise ConfigError(f"missing required key '{key}' in [{where}]")
    return section[key]


def resolve_path(base_dir: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


def storage_path(root_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(root_dir).as_posix()


def resolve_inside(root_dir: Path, value: str | Path, key: str, where: str) -> Path:
    path = resolve_path(root_dir, value)
    if not path.is_relative_to(root_dir):
        raise ConfigError(
            f"'{key}' in [{where}] resolves to {path}, which is outside "
            f"root_dir {root_dir}: paths stored in the database must stay inside the root"
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


def _read_text_file(path: str | Path, where: str) -> str:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"file not found: {path} (referenced by [{where}])")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ConfigError(f"file is empty: {path} (referenced by [{where}])")
    return text


def _load_asr(raw: dict, base_dir: Path) -> AsrConfig:
    section = _section(raw, "asr")
    transcript_raw = _section(section, "transcript", "asr.")
    where = "asr.transcript"
    return AsrConfig(
        repo_id=_require(section, "repo_id", "asr"),
        local_dir=resolve_path(base_dir, _require(section, "local_dir", "asr")),
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


def _load_llm(raw: dict, base_dir: Path) -> LlmConfig:
    section = _section(raw, "llm")
    output_raw = _section(section, "output", "llm.")
    return LlmConfig(
        repo_id=_require(section, "repo_id", "llm"),
        local_dir=resolve_path(base_dir, _require(section, "local_dir", "llm")),
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
            max_new_tokens=_require(output_raw, "max_new_tokens", "llm.output"),
            timeout_seconds=_require(output_raw, "timeout_seconds", "llm.output"),
        ),
    )


def _load_prompt(raw: dict, base_dir: Path) -> PromptConfig:
    section = _section(raw, "prompt")
    user_path = resolve_path(base_dir, _require(section, "user_file", "prompt"))
    user = _read_text_file(user_path, "prompt")
    for placeholder in PROMPT_PLACEHOLDERS:
        if "{" + placeholder + "}" not in user:
            raise ConfigError(
                f"user prompt {user_path} must contain the {{{placeholder}}} placeholder"
            )
    return PromptConfig(
        label=_require(section, "label", "prompt"),
        system=_read_text_file(
            resolve_path(base_dir, _require(section, "system_file", "prompt")), "prompt"
        ),
        user=user,
    )


def _load_reference(path: str | Path, entry_name: str) -> list[Reference]:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"{entry_name} file not found: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    entries = raw.get(entry_name, [])
    if not entries:
        raise ConfigError(f"at least one [[{entry_name}]] must be defined in {path}")

    references = []
    seen = set()
    for entry in entries:
        values = {
            field: _require(entry, field, entry_name)
            for field in (REFERENCE_CODE, REFERENCE_LABEL, REFERENCE_DESCRIPTION)
        }
        for field, value in values.items():
            if not isinstance(value, str) or not value.strip():
                raise ConfigError(
                    f"{entry_name} {field} must be a non-empty string in {path}, got {value!r}"
                )
        code = values[REFERENCE_CODE]
        if code in seen:
            raise ConfigError(f"duplicate {entry_name} code '{code}' in {path}")
        seen.add(code)
        references.append(Reference(**values))
    return references


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    base_dir = path.resolve().parent

    database_raw = _section(raw, "database")
    storage_raw = _section(raw, "storage")
    worker_raw = _section(raw, "worker")
    criteria_raw = _section(raw, "criteria")
    types_raw = _section(raw, "types")
    huggingface_raw = _section(raw, "huggingface")
    logging_raw = _section(raw, "logging")

    read_secret_file(
        resolve_path(base_dir, _require(huggingface_raw, "token_file", "huggingface"))
    )

    database = DatabaseConfig(
        dsn=read_secret_file(
            resolve_path(base_dir, _require(database_raw, "dsn_file", "database"))
        )
    )

    root_dir = resolve_path(base_dir, _require(storage_raw, "root_dir", "storage"))
    storage = StorageConfig(
        root_dir=root_dir,
        done_dir=resolve_inside(
            root_dir, _require(storage_raw, "done_dir", "storage"), "done_dir", "storage"
        ),
    )

    worker = WorkerConfig(
        count=_require(worker_raw, "count", "worker"),
        poll_interval_seconds=_require(worker_raw, "poll_interval_seconds", "worker"),
        max_attempts=_require(worker_raw, "max_attempts", "worker"),
    )

    asr = _load_asr(raw, base_dir)
    llm = _load_llm(raw, base_dir)

    logging_config = LoggingConfig(
        level=_require(logging_raw, "level", "logging"),
        dir=resolve_path(base_dir, _require(logging_raw, "dir", "logging")),
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
        prompt=_load_prompt(raw, base_dir),
        logging=logging_config,
        criteria=_load_reference(
            resolve_path(base_dir, _require(criteria_raw, "file", "criteria")), "criterion"
        ),
        call_types=_load_reference(
            resolve_path(base_dir, _require(types_raw, "file", "types")), "type"
        ),
    )
