import logging
import signal
import threading


class ShutdownRequested(Exception):
    pass


class LicenseExpired(ShutdownRequested):
    pass


logger = logging.getLogger(__name__)

_stop = threading.Event()


def install_handlers() -> None:
    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _handle)


def _handle(signum, frame) -> None:
    if not _stop.is_set():
        logger.info("received %s, finishing current work and stopping", signal.Signals(signum).name)
    _stop.set()


def is_stopping() -> bool:
    return _stop.is_set()


def check() -> None:
    if _stop.is_set():
        raise ShutdownRequested()


def sleep(seconds: float) -> None:
    if _stop.wait(seconds):
        raise ShutdownRequested()
