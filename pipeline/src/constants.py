LOG_FILE_TIME_FORMAT = "%Y%m%d-%H%M%S"
LOG_FILE_TEMPLATE = "pipeline-{timestamp}.log"
LOG_LATEST_NAME = "latest.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5
LOG_APPLICATION_LOGGERS = ("src", "__main__")
LOG_MODULE_DIR = "pipeline"
LOG_TRACE_LEVEL = 5
LOG_TRACE_NAME = "TRACE"
LOG_LEVELS = (LOG_TRACE_NAME, "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

SHUTDOWN_EXIT_CODE = 130
UNRECOVERABLE_EXIT_CODE = 70
CONFIG_EXIT_CODE = 1

STATUS_PENDING = "pending"
STATUS_TRANSCRIBED = "transcribed"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

STAGE_PRIORITY = (STATUS_TRANSCRIBED, STATUS_PENDING)

DONE_DIR_TEMPLATE = "%Y-%m/%d"

CRITERIA_TABLE = "criteria"
CALL_TYPES_TABLE = "call_types"
REFERENCE_LINE_TEMPLATE = "- {code} ({label}): {description}"

PROMPT_CRITERIA_PLACEHOLDER = "criteria"
PROMPT_TYPES_PLACEHOLDER = "types"
PROMPT_TRANSCRIPT_PLACEHOLDER = "transcript"
PROMPT_MANAGER_PLACEHOLDER = "manager"
UNKNOWN_MANAGER = "имя неизвестно"

ROLE_SYSTEM = "system"
ROLE_USER = "user"
JSON_RESPONSE_FORMAT = "json_object"
FINISH_REASON_LENGTH = "length"

KV_CACHE_TYPES = {
    "float32": 0,
    "float16": 1,
    "int8": 8,
    "int5": 7,
    "int4": 2,
}

GPU_LAYERS_PRESETS = {"none": 0, "all": -1}

BACKENDS_DIR = "/opt/llama"
BACKEND_CPU = "cpu"
BACKEND_GPU = "cuda"

ARCHITECTURE_KEY = "general.architecture"
BLOCK_COUNT_KEY = "{architecture}.block_count"
UNKNOWN_LAYERS = "an unknown number of"

CONTEXT_OVERFLOW_MARKER = "exceed context window"

ERROR_AUDIO_MISSING = "audio_missing"
ERROR_ASR_EMPTY = "asr_empty"
ERROR_TRANSCRIPT_EMPTY = "transcript_empty"
ERROR_LLM_TRUNCATED = "llm_truncated"
ERROR_LLM_PROMPT_TOO_LONG = "llm_prompt_too_long"
ERROR_LLM_INVALID_OUTPUT = "llm_invalid_output"
ERROR_NO_CRITERIA = "no_criteria"
ERROR_NO_CALL_TYPES = "no_call_types"
ERROR_UNKNOWN = "unknown"

DEVICE_FAILURE_MARKERS = ("out of memory", "cuda", "cublas", "cudnn")

SUSPICIOUS_COMPRESSION_RATIO = 2.4

MILLISECONDS_PER_SECOND = 1000
