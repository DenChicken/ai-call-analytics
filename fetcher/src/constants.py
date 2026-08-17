LOG_FILE_TIME_FORMAT = "%Y%m%d-%H%M%S"
LOG_FILE_TEMPLATE = "fetcher-{timestamp}.log"
LOG_LATEST_NAME = "latest.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5
LOG_APPLICATION_LOGGERS = ("src", "__main__")

TEMP_FILE_SUFFIX = ".part"

SHUTDOWN_EXIT_CODE = 130

STATUS_PENDING = "pending"

DIRECTION_OUTBOUND = "outbound"
DIRECTION_INBOUND = "inbound"
DIRECTION_CALLBACK = "callback"
DIRECTION_UNKNOWN = "unknown"
