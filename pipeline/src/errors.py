import torch

from src.constants import (
    DEVICE_FAILURE_MARKERS,
    ERROR_OUT_OF_MEMORY,
    ERROR_UNKNOWN,
)

DEVICE_UNUSABLE = (torch.OutOfMemoryError, MemoryError, torch.AcceleratorError)


class StageError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class UnrecoverableError(Exception):
    pass


def is_device_failure(error: BaseException) -> bool:
    if isinstance(error, DEVICE_UNUSABLE):
        return True
    if type(error) is not RuntimeError:
        return False
    message = str(error).lower()
    return any(marker in message for marker in DEVICE_FAILURE_MARKERS)


def classify(error: Exception) -> str:
    if isinstance(error, StageError):
        return error.code
    if is_device_failure(error):
        return ERROR_OUT_OF_MEMORY
    return ERROR_UNKNOWN
