import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

NAME_SEPARATOR = "_"
NAME_INVALID_PATTERN = re.compile(r"[^A-Za-z0-9]+")


def sanitize_name_part(value: str) -> str:
    return NAME_INVALID_PATTERN.sub(NAME_SEPARATOR, value).strip(NAME_SEPARATOR)


@dataclass(frozen=True)
class Agent:
    external_id: str
    display_name: str
    first_name: str | None = None
    last_name: str | None = None
    second_name: str | None = None
    email: str | None = None
    profile_link: str | None = None


@dataclass(frozen=True)
class Call:
    external_id: str
    started_at: datetime
    duration_seconds: int
    direction: str
    agent: Agent | None = None
    client_number: str | None = None
    subject: str | None = None
    crm_link: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CallBatch:
    calls: list[Call]
    cursor: str | None


class Source(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def list_calls(self, cursor: str | None, min_duration_seconds: int) -> CallBatch: ...

    @abstractmethod
    def build_file_name(self, call: Call, call_id: int) -> str: ...

    @abstractmethod
    def download_audio(self, call: Call, target: Path) -> None: ...

    @abstractmethod
    def close(self) -> None: ...
