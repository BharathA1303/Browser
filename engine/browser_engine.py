"""WebView2-driven browser engine orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from urllib.parse import quote_plus

from storage.history import HistoryManager
from utils.logger import get_logger


@dataclass
class NavigationResult:
    """Normalized navigation decision."""

    target_url: str
    is_internal: bool = False
    html_content: str = ""


class BrowserEngine:
    """Delegate URL normalization, history and internal pages for a tab."""

    def __init__(self, history_manager: HistoryManager | None = None) -> None:
        """Initialize tab-local engine state."""

        self.history = history_manager or HistoryManager()
        self.logger = get_logger("engine.browser_engine")
        self.last_known_url: str = ""
        self.last_known_title: str = ""

    def resolve_input(self, user_input: str) -> NavigationResult:
        """Resolve address-bar input into a URL or internal page action."""

        text = user_input.strip()
        if not text:
            return NavigationResult(target_url="https://www.google.com")

        if text.lower() == "browser://history":
            return NavigationResult(
                target_url="browser://history",
                is_internal=True,
                html_content=self.build_history_page_html(),
            )

        if text.startswith("http://") or text.startswith("https://"):
            return NavigationResult(target_url=text)

        if " " in text or "." not in text:
            query = quote_plus(text)
            return NavigationResult(target_url=f"https://www.google.com/search?q={query}")

        return NavigationResult(target_url=f"https://{text}")

    def record_visit(self, url: str, title: str = "") -> None:
        """Record a successful navigation in tab history."""

        normalized_url = url.strip()
        if not normalized_url:
            return

        if self.history.current() != normalized_url:
            self.history.visit(normalized_url)
        self.last_known_url = normalized_url
        self.last_known_title = title.strip()
        self.logger.info("Recorded visit %s", normalized_url)

    def build_history_page_html(self) -> str:
        """Generate the internal history page as plain HTML."""

        rows: list[str] = []
        for record in reversed(self.history.all_records()):
            url = escape(record.url)
            timestamp = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            rows.append(
                f'<li><a href="{url}">{url}</a> '
                f'<span style="color:#666">{timestamp}</span></li>'
            )

        if not rows:
            rows.append("<li>No history yet</li>")

        return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Browsing History</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 18px; background: #fafafa; }
    h1 { margin: 0 0 12px 0; }
    ul { line-height: 1.6; }
    a { color: #0645ad; }
  </style>
</head>
<body>
  <h1>Browsing History</h1>
  <p>Click an entry to open it.</p>
  <ul>
    %s
  </ul>
</body>
</html>
""" % "\n    ".join(rows)
