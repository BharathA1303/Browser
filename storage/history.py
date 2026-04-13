"""Browsing history with back/forward navigation support."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class HistoryRecord:
    """A single visit entry in history."""

    url: str
    timestamp: datetime


class HistoryManager:
    """Maintain linear browsing history and cursor position."""

    def __init__(self) -> None:
        """Initialize empty history state."""

        self._records: List[HistoryRecord] = []
        self._index: int = -1

    def visit(self, url: str) -> None:
        """Record a fresh page visit and truncate forward stack."""

        if self._index < len(self._records) - 1:
            self._records = self._records[: self._index + 1]
        self._records.append(HistoryRecord(url=url, timestamp=datetime.utcnow()))
        self._index = len(self._records) - 1

    def back(self) -> Optional[str]:
        """Move to previous history entry and return its URL."""

        if self._index > 0:
            self._index -= 1
            return self._records[self._index].url
        return None

    def forward(self) -> Optional[str]:
        """Move to next history entry and return its URL."""

        if self._index < len(self._records) - 1:
            self._index += 1
            return self._records[self._index].url
        return None

    def current(self) -> Optional[str]:
        """Return the current URL if available."""

        if 0 <= self._index < len(self._records):
            return self._records[self._index].url
        return None

    def all_records(self) -> List[HistoryRecord]:
        """Return a copy of all history records."""

        return list(self._records)
