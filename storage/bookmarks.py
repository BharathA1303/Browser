"""Bookmark persistence manager."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import List


@dataclass
class BookmarkEntry:
    """Represents one stored bookmark entry."""

    url: str
    title: str = ""


class BookmarksManager:
    """Save and load bookmarks in JSON format."""

    def __init__(self, file_path: str = "bookmarks.json") -> None:
        """Initialize manager and storage path."""

        self.path = Path(file_path)

    def load(self) -> List[BookmarkEntry]:
        """Load bookmark list from disk."""

        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                bookmarks: List[BookmarkEntry] = []
                for item in data:
                    if isinstance(item, str):
                        bookmarks.append(BookmarkEntry(url=item, title=item))
                    elif isinstance(item, dict):
                        url = str(item.get("url", "")).strip()
                        title = str(item.get("title", url)).strip() or url
                        if url:
                            bookmarks.append(BookmarkEntry(url=url, title=title))
                return bookmarks
        except json.JSONDecodeError:
            return []
        return []

    def save(self, bookmarks: List[BookmarkEntry]) -> None:
        """Persist bookmarks list to disk."""

        unique: dict[str, BookmarkEntry] = {}
        for bookmark in bookmarks:
            if bookmark.url:
                unique[bookmark.url] = bookmark
        payload = [asdict(bookmark) for bookmark in unique.values()]
        payload.sort(key=lambda item: item["title"].lower())
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add(self, url: str, title: str = "") -> None:
        """Add a bookmark if missing."""

        bookmarks = self.load()
        if not any(bookmark.url == url for bookmark in bookmarks):
            bookmarks.append(BookmarkEntry(url=url, title=title or url))
            self.save(bookmarks)

    def remove(self, url: str) -> None:
        """Remove a bookmark if present."""

        bookmarks = [item for item in self.load() if item.url != url]
        self.save(bookmarks)
