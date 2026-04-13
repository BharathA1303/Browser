"""Bookmark persistence manager."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List


class BookmarksManager:
    """Save and load bookmarks in JSON format."""

    def __init__(self, file_path: str = "bookmarks.json") -> None:
        """Initialize manager and storage path."""

        self.path = Path(file_path)

    def load(self) -> List[str]:
        """Load bookmark list from disk."""

        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(item) for item in data]
        except json.JSONDecodeError:
            return []
        return []

    def save(self, bookmarks: List[str]) -> None:
        """Persist bookmarks list to disk."""

        unique = sorted(set(bookmarks))
        self.path.write_text(json.dumps(unique, indent=2), encoding="utf-8")

    def add(self, url: str) -> None:
        """Add a bookmark if missing."""

        bookmarks = self.load()
        if url not in bookmarks:
            bookmarks.append(url)
            self.save(bookmarks)

    def remove(self, url: str) -> None:
        """Remove a bookmark if present."""

        bookmarks = [item for item in self.load() if item != url]
        self.save(bookmarks)
