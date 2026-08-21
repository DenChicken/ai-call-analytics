import psycopg
import torch

from src.constants import (
    ERROR_DATABASE,
    ERROR_OUT_OF_MEMORY,
    ERROR_UNKNOWN,
)


class StageError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def classify(error: Exception) -> str:
    if isinstance(error, StageError):
        return error.code
    if isinstance(error, torch.cuda.OutOfMemoryError | MemoryError):
        return ERROR_OUT_OF_MEMORY
    if isinstance(error, psycopg.Error):
        return ERROR_DATABASE
    return ERROR_UNKNOWN
