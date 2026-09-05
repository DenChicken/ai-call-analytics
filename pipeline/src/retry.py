import functools
import logging

import psycopg

from src import shutdown
from src.errors import UnrecoverableError

logger = logging.getLogger(__name__)


def retried(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        config = self._config
        for attempt in range(config.max_retries):
            try:
                return method(self, *args, **kwargs)
            except psycopg.Error as error:
                if attempt + 1 == config.max_retries:
                    raise UnrecoverableError(
                        f"{method.__name__} failed after {config.max_retries} attempts, "
                        f"database is unreachable: {error}"
                    ) from error
                delay = min(
                    config.backoff_base_seconds * (2**attempt),
                    config.backoff_max_seconds,
                )
                logger.warning(
                    "%s failed (%s), retrying in %.1fs", method.__name__, error, delay
                )
                shutdown.sleep(delay)

    return wrapper
