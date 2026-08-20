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
STATUS_FAILED = "failed"

QUEUE_STATUSES = (
    STATUS_PENDING,
    STATUS_TRANSCRIBING,
    STATUS_TRANSCRIBED,
    STATUS_ANALYZING,
    STATUS_FAILED,
)
