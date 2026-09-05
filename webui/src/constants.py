LOG_FILE_TIME_FORMAT = "%Y%m%d-%H%M%S"
LOG_FILE_TEMPLATE = "webui-{timestamp}.log"
LOG_LATEST_NAME = "latest.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5
LOG_APPLICATION_LOGGERS = ("src", "__main__")
LOG_MODULE_DIR = "webui"
LOG_TRACE_LEVEL = 5
LOG_TRACE_NAME = "TRACE"
LOG_LEVELS = (LOG_TRACE_NAME, "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

STATUS_PENDING = "pending"
STATUS_TRANSCRIBING = "transcribing"
STATUS_TRANSCRIBED = "transcribed"
STATUS_ANALYZING = "analyzing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

QUEUE_STATUSES = (
    STATUS_PENDING,
    STATUS_TRANSCRIBING,
    STATUS_TRANSCRIBED,
    STATUS_ANALYZING,
    STATUS_FAILED,
)

ERROR_AUDIO_MISSING = "audio_missing"
ERROR_ASR_EMPTY = "asr_empty"
ERROR_TRANSCRIPT_EMPTY = "transcript_empty"
ERROR_LLM_TRUNCATED = "llm_truncated"
ERROR_LLM_PROMPT_TOO_LONG = "llm_prompt_too_long"
ERROR_LLM_INVALID_OUTPUT = "llm_invalid_output"
ERROR_NO_CRITERIA = "no_criteria"
ERROR_NO_CALL_TYPES = "no_call_types"
ERROR_OUT_OF_MEMORY = "out_of_memory"
ERROR_DATABASE = "database"
ERROR_STALE_CLAIM = "stale_claim"
ERROR_UNKNOWN = "unknown"

APP_TITLE = "Аналитика звонков"

CONFIG_ENV_VAR = "WEBUI_CONFIG"
LOG_FILE_ENV_VAR = "WEBUI_LOG_FILE"
FRONTEND_PORT_ENV_VAR = "FRONTEND_PORT"
BACKEND_PORT_ENV_VAR = "BACKEND_PORT"
DEFAULT_FRONTEND_PORT = 3000
DEFAULT_BACKEND_PORT = 8000
REFLEX_MODULE = "reflex"
REFLEX_RUN_COMMAND = "run"
REFLEX_FRONTEND_PORT_FLAG = "--frontend-port"
REFLEX_BACKEND_PORT_FLAG = "--backend-port"
REFLEX_BACKEND_PATH_ENV_VAR = "REFLEX_BACKEND_PATH"
REFLEX_API_URL_ENV_VAR = "REFLEX_API_URL"

SHUTDOWN_EXIT_CODE = 130
UNRECOVERABLE_EXIT_CODE = 70
DATABASE_CONNECT_TIMEOUT = 10
WINDOWS_PLATFORM = "win32"
TASKKILL_COMMAND = "taskkill"
TASKKILL_TREE_FLAGS = ("/T", "/F", "/PID")
TERMINATE_TIMEOUT_SECONDS = 10

PORT_PROBE_HOST = "0.0.0.0"
SAME_DOMAIN_HOST = "localhost"
SAME_DOMAIN_SCHEME = "http"
STARTUP_ACCESS_NOTE = (
    "reachable from other machines at http://<this-host>:{port} "
    "once both ports are open"
)

SESSION_COOKIE_NAME = "webui_session"
SESSION_SAME_SITE = "strict"
SESSION_TOKEN_BYTES = 32
SESSION_MAX_AGE_SECONDS = 604800
SESSION_COOKIE_SECURE = False

FIELD_LOGIN = "login"
FIELD_PASSWORD = "password"

LICENSE_UNAVAILABLE_MESSAGE = "license unavailable"

LOGIN_ERROR_MESSAGE = "Неверный логин или пароль"
INTERNAL_ERROR_MESSAGE = "Сервис временно недоступен"
LOAD_ERROR_MESSAGE = "Не удалось загрузить данные"
LICENSE_EXPIRED_MESSAGE = "Срок действия лицензии истёк. Обратитесь к поставщику: {contact}"

ROUTE_LOGIN = "/login"
ROUTE_DASHBOARD = "/"
ROUTE_MANAGERS = "/managers"
ROUTE_MANAGER = "/manager"
ROUTE_CALLS = "/calls"
ROUTE_CALL = "/call"
NOT_FOUND_ROUTE = "404"

SECTION_DASHBOARD = "Дашборд"
SECTION_CALLS = "Звонки"
SECTION_MANAGERS = "Менеджеры"
ALL_CALLS_LABEL = "Все звонки"

CHART_MARGIN = {"left": 10, "right": 20}
CHART_TICK_COUNT = 6
CRM_ICON_SIZE = 14
MUTED_COLOR = "var(--gray-9)"
FULL_HEIGHT = "100vh"

STATUS_LABELS = {
    STATUS_PENDING: "Ожидает",
    STATUS_TRANSCRIBING: "Расшифровка",
    STATUS_TRANSCRIBED: "Расшифрован",
    STATUS_ANALYZING: "Анализ",
    STATUS_DONE: "Готово",
    STATUS_FAILED: "Ошибка",
}

STATUS_ORDER = (
    STATUS_PENDING,
    STATUS_TRANSCRIBING,
    STATUS_TRANSCRIBED,
    STATUS_ANALYZING,
    STATUS_DONE,
    STATUS_FAILED,
)

PAGE_SIZES = (25, 50, 100)

DEFAULT_STATUS_COLOR = "gray"

STATUS_COLORS = {
    STATUS_PENDING: "gray",
    STATUS_TRANSCRIBING: "blue",
    STATUS_TRANSCRIBED: "blue",
    STATUS_ANALYZING: "amber",
    STATUS_DONE: "grass",
    STATUS_FAILED: "red",
}

PERIOD_TODAY = "today"
PERIOD_WEEK = "7d"
PERIOD_MONTH = "30d"

PERIOD_DAYS = {
    PERIOD_TODAY: 1,
    PERIOD_WEEK: 7,
    PERIOD_MONTH: 30,
}

PERIOD_LABELS = {
    PERIOD_TODAY: "Сегодня",
    PERIOD_WEEK: "7 дней",
    PERIOD_MONTH: "30 дней",
}

PERIOD_BY_LABEL = {label: code for code, label in PERIOD_LABELS.items()}

PARAM_PERIOD = "period"
PARAM_AGENT = "agent"
PARAM_TYPES = "types"
PARAM_STATUSES = "statuses"
PARAM_PAGE = "page"
PARAM_SEARCH = "search"
PARAM_SORT = "sort"
PARAM_DESC = "desc"

TYPES_LABEL = "Типы звонков"
STATUSES_LABEL = "Статусы"
TYPES_SUMMARY_TEMPLATE = "Типы: {selected}/{total}"
STATUSES_SUMMARY_TEMPLATE = "Статусы: {selected}/{total}"

PERCENT_SCALE = 100
SHARE_PRECISION = 2
SHARE_MAX = 1.0
SCORE_FRACTION_TEMPLATE = "{met}/{total}"
DELTA_TEMPLATE = "{sign}{value} п.п."
POSITIVE_SIGN = "+"
NEGATIVE_SIGN = "-"
EMPTY_VALUE = "—"

DATETIME_LABEL_FORMAT = "%d.%m.%Y %H:%M"
DAY_LABEL_FORMAT = "%d.%m"
WEEKDAY_NAMES = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
DATETIME_FULL_TEMPLATE = "{moment} ({weekday})"
UTC_OFFSET_TEMPLATE = "UTC{sign}{hours}"
OFFSET_COOKIE_NAME = "webui_offset"
SIDEBAR_COOKIE_NAME = "webui_sidebar"
SIDEBAR_COLLAPSED_VALUE = "collapsed"
MIN_UTC_OFFSET = -11
MAX_UTC_OFFSET = 14
FALLBACK_UTC_OFFSET = 0
TIMEZONE_LABEL = "Часовой пояс"
BROWSER_OFFSET_SCRIPT = "-new Date().getTimezoneOffset() / 60"
RELOAD_SCRIPT = "window.location.reload()"
TIMEZONE_DIALOG_TITLE = "Сменить часовой пояс?"
TIMEZONE_DIALOG_TEXT = (
    "Страница перезагрузится. Метки времени, границы периода и группировка "
    "по дням будут пересчитаны: звонок у границы суток может перейти "
    "на соседний день, а «сегодня» — сместиться."
)
TIMEZONE_DIALOG_CONFIRM = "Сменить"
TIMEZONE_DIALOG_CANCEL = "Отмена"
DURATION_TEMPLATE = "{minutes}:{seconds:02d}"
SECONDS_PER_MINUTE = 60
MILLISECONDS_PER_SECOND = 1000

AUDIO_ROUTE = "/audio"
AUDIO_MEDIA_TYPE = "audio/mpeg"
AUDIO_ELEMENT_ID = "call-audio"
