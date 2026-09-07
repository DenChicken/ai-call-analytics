import torch

from src.constants import DEVICE_FAILURE_MARKERS, ERROR_UNKNOWN

DEVICE_ERRORS = (torch.OutOfMemoryError, MemoryError, torch.AcceleratorError)


class CallError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class FatalError(Exception):
    pass


def is_device_failure(error: BaseException) -> bool:
    if isinstance(error, DEVICE_ERRORS):
        return True
    if type(error) is not RuntimeError:
        return False
    message = str(error).lower()
    return any(marker in message for marker in DEVICE_FAILURE_MARKERS)


def error_code(error: Exception) -> str:
    return error.code if isinstance(error, CallError) else ERROR_UNKNOWN
