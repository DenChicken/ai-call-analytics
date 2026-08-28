import logging

from src.constants import LOG_TRACE_LEVEL, LOG_TRACE_NAME


def _trace(self: logging.Logger, message: str, *args, **kwargs) -> None:
    if self.isEnabledFor(LOG_TRACE_LEVEL):
        self._log(LOG_TRACE_LEVEL, message, args, **kwargs)


logging.addLevelName(LOG_TRACE_LEVEL, LOG_TRACE_NAME)
logging.Logger.trace = _trace
