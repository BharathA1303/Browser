"""WebView2-driven browser engine orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from urllib.parse import quote_plus
from datetime import datetime

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

    def can_go_back(self) -> bool:
        """Return True if the current tab can navigate backward."""

        return getattr(self.history, "_index", -1) > 0

    def can_go_forward(self) -> bool:
        """Return True if the current tab can navigate forward."""

        index = getattr(self.history, "_index", -1)
        records = getattr(self.history, "_records", [])
        return 0 <= index < (len(records) - 1)

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

    def build_new_tab_page_html(self) -> str:
        """Generate a dark themed new-tab start page with search and quick links."""

        now = datetime.now().strftime("%H:%M")
        return f"""
<!doctype html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>New Tab</title>
    <style>
        :root {{
            color-scheme: dark;
            --bg: #1e1e2e;
            --panel: #313244;
            --panel-2: #45475a;
            --text: #cdd6f4;
            --muted: #a6adc8;
            --accent: #89b4fa;
        }}
        html, body {{ height: 100%; margin: 0; }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: Segoe UI, Arial, sans-serif;
            display: grid;
            place-items: center;
        }}
        .wrap {{ text-align: center; width: min(860px, calc(100vw - 40px)); }}
        .clock {{ font-size: 42px; font-weight: 600; margin-bottom: 22px; letter-spacing: 1px; }}
        .search {{
            display: flex; align-items: center; gap: 10px;
            background: var(--panel); border: 1px solid rgba(205,214,244,0.12);
            border-radius: 18px; padding: 14px 18px; box-shadow: 0 10px 30px rgba(0,0,0,0.22);
        }}
        .search input {{
            flex: 1; border: 0; outline: 0; background: transparent; color: var(--text);
            font-size: 18px;
        }}
        .search input::placeholder {{ color: var(--muted); }}
        .search button {{
            border: 0; border-radius: 12px; padding: 10px 14px; cursor: pointer;
            background: var(--panel-2); color: var(--text); font-weight: 600;
        }}
        .links {{ display: flex; gap: 12px; justify-content: center; margin-top: 22px; flex-wrap: wrap; }}
        .links a {{
            text-decoration: none; color: var(--text); background: var(--panel);
            border: 1px solid rgba(205,214,244,0.12); padding: 10px 16px; border-radius: 14px;
        }}
        .links a:hover {{ border-color: var(--accent); box-shadow: 0 0 0 1px rgba(137,180,250,0.35); }}
        .hint {{ margin-top: 18px; color: var(--muted); font-size: 13px; }}
    </style>
    <script>
        function submitSearch() {{
            const value = document.getElementById('search').value || '';
            if (window.pywebview && window.pywebview.api) {{
                window.pywebview.api.navigate(value);
            }}
        }}
        function tick() {{
            const d = new Date();
            const time = d.toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit' }});
            document.getElementById('clock').textContent = time;
        }}
        window.addEventListener('DOMContentLoaded', function() {{
            tick(); setInterval(tick, 1000);
            const input = document.getElementById('search');
            input.addEventListener('keydown', function(ev) {{ if (ev.key === 'Enter') submitSearch(); }});
        }});
    </script>
</head>
<body>
    <div class="wrap">
        <div id="clock" class="clock">{now}</div>
        <div class="search">
            <span>🔎</span>
            <input id="search" type="text" placeholder="Search Google or type a URL" />
            <button onclick="submitSearch()">Search</button>
        </div>
        <div class="links">
            <a href="#" onclick="window.pywebview.api.navigate('https://www.google.com'); return false;">Google</a>
            <a href="#" onclick="window.pywebview.api.navigate('https://www.youtube.com'); return false;">YouTube</a>
            <a href="#" onclick="window.pywebview.api.navigate('https://github.com'); return false;">GitHub</a>
            <a href="#" onclick="window.pywebview.api.navigate('https://en.wikipedia.org'); return false;">Wikipedia</a>
        </div>
        <div class="hint">Type keywords to search Google or enter a URL.</div>
    </div>
</body>
</html>
"""
