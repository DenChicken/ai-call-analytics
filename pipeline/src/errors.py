import psycopg
import torch

from src.constants import (
    ERROR_DATABASE,
    ERROR_OUT_OF_MEMORY,
    ERROR_UNKNOWN,
)

DEVICE_UNUSABLE = (torch.OutOfMemoryError, MemoryError, torch.AcceleratorError)


class StageError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def classify(error: Exception) -> str:
    if isinstance(error, StageError):
        return error.code
    if isinstance(error, torch.OutOfMemoryError | MemoryError):
        return ERROR_OUT_OF_MEMORY
    if isinstance(error, psycopg.Error):
        return ERROR_DATABASE
    return ERROR_UNKNOWN
