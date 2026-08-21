LOG_FILE_TIME_FORMAT = "%Y%m%d-%H%M%S"
LOG_FILE_TEMPLATE = "webui-{timestamp}.log"
LOG_LATEST_NAME = "latest.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5
LOG_APPLICATION_LOGGERS = ("src", "__main__")

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

APP_TITLE = "Аналитика звонков"

CONFIG_ENV_VAR = "WEBUI_CONFIG"
LOG_FILE_ENV_VAR = "WEBUI_LOG_FILE"
REFLEX_MODULE = "reflex"
REFLEX_RUN_COMMAND = "run"

SESSION_COOKIE_NAME = "webui_session"
SESSION_SAME_SITE = "strict"

FIELD_LOGIN = "login"
FIELD_PASSWORD = "password"

LOGIN_ERROR_MESSAGE = "Неверный логин или пароль"

ROUTE_LOGIN = "/login"
ROUTE_DASHBOARD = "/"
ROUTE_MANAGERS = "/managers"
ROUTE_MANAGER = "/manager"
ROUTE_CALL = "/call"

STATUS_LABELS = {
    STATUS_PENDING: "Ожидает",
    STATUS_TRANSCRIBING: "Расшифровка",
    STATUS_TRANSCRIBED: "Расшифрован",
    STATUS_ANALYZING: "Анализ",
    STATUS_DONE: "Готово",
    STATUS_FAILED: "Ошибка",
}

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

PERCENT_SCALE = 100
SCORE_FRACTION_TEMPLATE = "{met}/{total}"
DELTA_TEMPLATE = "{sign}{value} п.п."
TRANSITION_ARROW = "→"
POSITIVE_SIGN = "+"
EMPTY_VALUE = "—"

DATETIME_LABEL_FORMAT = "%d.%m %H:%M"
DAY_LABEL_FORMAT = "%d.%m"
DURATION_TEMPLATE = "{minutes}:{seconds:02d}"
SECONDS_PER_MINUTE = 60
MILLISECONDS_PER_SECOND = 1000

AUDIO_ROUTE = "/audio"
AUDIO_MEDIA_TYPE = "audio/mpeg"
