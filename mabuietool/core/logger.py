"""Central logging primitives for MabuiETool GUI and services."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable


class LogCategory(str, Enum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    DEBUG = "DEBUG"
    USB = "USB"
    PROTOCOL = "PROTOCOL"
    DEVICE = "DEVICE"


@dataclass(frozen=True)
class LogRecord:
    timestamp: datetime
    category: LogCategory
    message: str

    def format(self) -> str:
        return f"[{self.timestamp:%H:%M:%S}] [{self.category.value}] {self.message}"


class AppLogger:
    def __init__(self) -> None:
        self._records: list[LogRecord] = []
        self._subscribers: list[Callable[[LogRecord], None]] = []

    def subscribe(self, callback: Callable[[LogRecord], None]) -> None:
        self._subscribers.append(callback)

    def log(self, category: LogCategory | str, message: str) -> LogRecord:
        if isinstance(category, str):
            category = LogCategory(category)
        record = LogRecord(datetime.now(), category, message)
        self._records.append(record)
        for callback in list(self._subscribers):
            callback(record)
        return record

    def records(self) -> Iterable[LogRecord]:
        return tuple(self._records)

    def clear(self) -> None:
        self._records.clear()


app_logger = AppLogger()
