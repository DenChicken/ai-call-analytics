LOG_FILE_TIME_FORMAT = "%Y%m%d-%H%M%S"
LOG_FILE_TEMPLATE = "pipeline-{timestamp}.log"
LOG_LATEST_NAME = "latest.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

DONE_MONTH_FORMAT = "%Y-%m"
DONE_DAY_FORMAT = "%d"

SCORE_MIN = 0
SCORE_MAX = 1

SPEAKER_AGENT = "agent"
SPEAKER_CLIENT = "client"
SPEAKER_UNKNOWN_TEMPLATE = "speaker_{index}"
