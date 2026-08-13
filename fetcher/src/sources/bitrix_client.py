import logging
import time
from pathlib import Path

import httpx

from src.config import NetworkConfig

RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)
RETRYABLE_ERROR_CODES = ("QUERY_LIMIT_EXCEEDED", "OPERATION_TIME_LIMIT")
BATCH_METHOD = "batch"
BATCH_MAX_COMMANDS = 50
JSON_SUFFIX = ".json"

logger = logging.getLogger(__name__)


class BitrixError(Exception):
    pass


class RateLimiter:
    def __init__(self, requests_per_second: float):
        self._min_interval = 1.0 / requests_per_second
        self._last_call = 0.0

    def wait(self) -> None:
        remaining = self._min_interval - (time.monotonic() - self._last_call)
        if remaining > 0:
            time.sleep(remaining)
        self._last_call = time.monotonic()


class BitrixClient:
    def __init__(self, rest_url: str, network: NetworkConfig):
        self._rest_url = rest_url.rstrip("/") + "/"
        self._network = network
        self._limiter = RateLimiter(network.requests_per_second)
        self._client = httpx.Client(
            timeout=httpx.Timeout(network.read_timeout, connect=network.connect_timeout),
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def _backoff_delay(self, attempt: int) -> float:
        return min(
            self._network.backoff_base_seconds * (2**attempt),
            self._network.backoff_max_seconds,
        )

    def call(self, method: str, params: dict) -> dict:
        url = self._rest_url + method + JSON_SUFFIX

        for attempt in range(self._network.max_retries):
            self._limiter.wait()
            try:
                response = self._client.post(url, json=params)
            except httpx.RequestError as error:
                delay = self._backoff_delay(attempt)
                logger.warning("request to %s failed (%s), retrying in %.1fs", method, error, delay)
                time.sleep(delay)
                continue

            if response.status_code in RETRYABLE_STATUS_CODES:
                delay = self._backoff_delay(attempt)
                logger.warning(
                    "method %s returned %s, retrying in %.1fs", method, response.status_code, delay
                )
                time.sleep(delay)
                continue

            if response.status_code != httpx.codes.OK:
                raise BitrixError(f"{method} returned HTTP {response.status_code}")

            body = response.json()
            error_code = body.get("error")
            if error_code in RETRYABLE_ERROR_CODES:
                delay = self._backoff_delay(attempt)
                logger.warning("method %s returned %s, retrying in %.1fs", method, error_code, delay)
                time.sleep(delay)
                continue
            if error_code:
                raise BitrixError(f"{method} returned {error_code}: {body.get('error_description')}")

            return body

        raise BitrixError(f"{method} failed after {self._network.max_retries} attempts")

    def call_batch(self, commands: dict[str, str]) -> dict:
        results = {}
        keys = list(commands)
        for offset in range(0, len(keys), BATCH_MAX_COMMANDS):
            chunk = {key: commands[key] for key in keys[offset : offset + BATCH_MAX_COMMANDS]}
            body = self.call(BATCH_METHOD, {"halt": 0, "cmd": chunk})
            result = body.get("result") or {}
            errors = result.get("result_error")
            if isinstance(errors, dict):
                for key, error in errors.items():
                    logger.warning("batch command %s failed: %s", key, error)
            entries = result.get("result")
            if isinstance(entries, dict):
                results.update(entries)
        return results

    def download(self, url: str, target: Path) -> None:
        with self._client.stream("GET", url, timeout=self._network.download_timeout) as response:
            response.raise_for_status()
            with target.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
