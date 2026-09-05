import torch

from src.constants import (
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


def classify(error: Exception) -> str:
    if isinstance(error, StageError):
        return error.code
    if isinstance(error, DEVICE_UNUSABLE):
        return ERROR_OUT_OF_MEMORY
    return ERROR_UNKNOWN
