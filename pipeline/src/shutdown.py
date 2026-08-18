import signal
import threading


class ShutdownRequested(Exception):
    pass


_stop = threading.Event()


def install_handlers() -> None:
    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _handle)


def _handle(signum, frame) -> None:
    _stop.set()


def is_stopping() -> bool:
    return _stop.is_set()


def check() -> None:
    if _stop.is_set():
        raise ShutdownRequested()


def sleep(seconds: float) -> None:
    if _stop.wait(seconds):
        raise ShutdownRequested()
