"""Pywebview-only browser UI with separate toolbar and content windows."""

from __future__ import annotations

import ctypes
import json
import threading
import time
from dataclasses import dataclass

import webview

from engine.browser_engine import BrowserEngine
from storage.bookmarks import BookmarksManager
from utils.logger import get_logger


@dataclass
class _BrowserState:
    """Current page state used by the toolbar window."""

    url: str
    title: str
    status: str


class _ToolbarApi:
    """JS bridge API exposed to the toolbar WebView window."""

    def __init__(self, app: "BrowserWindow") -> None:
        self._app = app

    def navigate(self, text: str) -> None:
        self._app.navigate(text)

    def back(self) -> None:
        self._app.go_back()

    def forward(self) -> None:
        self._app.go_forward()

    def refresh(self) -> None:
        self._app.refresh()

    def bookmark(self) -> None:
        self._app.add_bookmark()

    def get_state(self) -> dict[str, str]:
        return self._app.get_toolbar_state()


class BrowserWindow:
    """Main browser app coordinating two pywebview windows."""

    HOME_URL = "https://www.google.com"
    TOOLBAR_HEIGHT = 80

    def __init__(self) -> None:
        self.logger = get_logger("ui.window")
        self.engine = BrowserEngine()
        self.bookmarks = BookmarksManager()
        self.state = _BrowserState(url=self.HOME_URL, title="Google", status="Starting...")
        self._closing = False

        screen_width = ctypes.windll.user32.GetSystemMetrics(0)
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)

        self.toolbar_api = _ToolbarApi(self)
        self.toolbar_window = webview.create_window(
            title="Browser Toolbar",
            html=self._build_toolbar_html(),
            width=screen_width,
            height=self.TOOLBAR_HEIGHT,
            x=0,
            y=0,
            resizable=False,
            frameless=True,
            on_top=True,
            confirm_close=False,
            background_color="#1e1e2e",
            js_api=self.toolbar_api,
        )

        self.content_window = webview.create_window(
            title="Browser v1",
            url=self.HOME_URL,
            width=screen_width,
            height=max(400, screen_height - self.TOOLBAR_HEIGHT),
            x=0,
            y=self.TOOLBAR_HEIGHT,
            resizable=True,
            confirm_close=False,
            background_color="#11111b",
        )

        self.content_window.events.loaded += self._on_content_loaded
        self.content_window.events.closed += self.close
        self.toolbar_window.events.closed += self.close

    def run(self) -> None:
        """Run pywebview (must be main thread on Windows)."""

        webview.start(self._bootstrap, self.content_window, debug=False, gui="edgechromium")

    def close(self) -> None:
        """Close both windows cleanly."""

        if self._closing:
            return
        self._closing = True

        try:
            self.toolbar_window.destroy()
        except Exception:
            pass

        try:
            self.content_window.destroy()
        except Exception:
            pass

    def navigate(self, user_input: str) -> None:
        """Navigate main content window using address-bar input."""

        if self._closing:
            return

        nav = self.engine.resolve_input(user_input)
        self.state.status = "Loading..."

        try:
            if nav.is_internal and nav.target_url == "browser://history":
                self.content_window.load_html(nav.html_content)
                self.state.url = nav.target_url
                self.state.title = "Browsing History"
                return

            self.content_window.load_url(nav.target_url)
        except Exception as error:  # noqa: BLE001
            self.logger.warning("Navigation failed: %s", error)
            self.state.status = "Navigation failed"

    def go_back(self) -> None:
        """Trigger browser history back."""

        try:
            self.content_window.evaluate_js("history.back();")
        except Exception as error:  # noqa: BLE001
            self.logger.warning("Back failed: %s", error)

    def go_forward(self) -> None:
        """Trigger browser history forward."""

        try:
            self.content_window.evaluate_js("history.forward();")
        except Exception as error:  # noqa: BLE001
            self.logger.warning("Forward failed: %s", error)

    def refresh(self) -> None:
        """Reload current page."""

        try:
            if self.state.url == "browser://history":
                self.content_window.load_html(self.engine.build_history_page_html())
            else:
                self.content_window.evaluate_js("location.reload();")
        except Exception as error:  # noqa: BLE001
            self.logger.warning("Refresh failed: %s", error)

    def add_bookmark(self) -> None:
        """Save bookmark from current page state."""

        if self.state.url:
            self.bookmarks.add(self.state.url, self.state.title or self.state.url)
            self.state.status = "Bookmark saved"

    def get_toolbar_state(self) -> dict[str, str]:
        """Return current state for toolbar UI polling."""

        return {
            "url": self.state.url,
            "title": self.state.title,
            "status": self.state.status,
            "secure": "1" if self.state.url.startswith("https://") else "0",
        }

    def _bootstrap(self, _window: webview.Window) -> None:
        """Start sync worker after pywebview loop starts."""

        self.state.status = "Ready"
        thread = threading.Thread(target=self._sync_windows_worker, daemon=True, name="toolbar-sync")
        thread.start()

    def _sync_windows_worker(self) -> None:
        """Keep toolbar aligned above content window and refresh title/url state."""

        while not self._closing:
            try:
                x = self.content_window.x
                y = self.content_window.y
                width = self.content_window.width

                toolbar_y = max(0, y - self.TOOLBAR_HEIGHT)
                self.toolbar_window.move(x, toolbar_y)
                self.toolbar_window.resize(width, self.TOOLBAR_HEIGHT)

                current_url = self.content_window.get_current_url() or self.state.url
                if current_url:
                    self.state.url = current_url

                if self.state.url.startswith("https://"):
                    self.state.status = "Secure"
                else:
                    self.state.status = "Ready"
            except Exception:
                pass

            time.sleep(0.15)

    def _on_content_loaded(self) -> None:
        """Update URL/title/history after navigation."""

        if self._closing:
            return

        try:
            current_url = self.content_window.get_current_url() or self.state.url
            self.state.url = current_url
        except Exception:
            current_url = self.state.url

        title = self.state.title
        try:
            value = self.content_window.evaluate_js("document.title")
            if isinstance(value, str) and value.strip():
                title = value.strip()
        except Exception:
            pass

        self.state.title = title
        self.state.status = "Done"
        self.content_window.set_title(f"{self.state.title or self.state.url} - Browser v1")

        if current_url and current_url not in {"about:blank", "browser://history"}:
            self.engine.record_visit(current_url, title)

    def _build_toolbar_html(self) -> str:
        """Return static toolbar HTML UI for the separate top window."""

        return f"""
<!doctype html>
<html>
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>Toolbar</title>
<style>
  body {{ margin: 0; background: #1e1e2e; color: #cdd6f4; font-family: Segoe UI, Arial, sans-serif; overflow: hidden; }}
  .shell {{ height: 80px; display: flex; flex-direction: column; }}
  .tabs {{ height: 35px; display: flex; align-items: center; padding: 6px 10px 2px; box-sizing: border-box; }}
  .tab {{ background: #313244; border-radius: 10px 10px 4px 4px; padding: 6px 12px; max-width: 280px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .bar {{ height: 45px; display: grid; grid-template-columns: auto auto auto 1fr auto auto; gap: 8px; align-items: center; padding: 4px 10px 8px; box-sizing: border-box; }}
  button {{ background: #313244; color: #cdd6f4; border: 0; border-radius: 8px; height: 30px; min-width: 34px; cursor: pointer; }}
  .address {{ background: #313244; border-radius: 12px; display: grid; grid-template-columns: auto 1fr; align-items: center; height: 32px; padding: 0 10px; }}
  .addr {{ border: 0; outline: 0; background: transparent; color: #cdd6f4; width: 100%; }}
  .status {{ color: #a6adc8; font-size: 12px; text-align: right; min-width: 90px; }}
</style>
</head>
<body>
  <div class=\"shell\">
    <div class=\"tabs\"><div class=\"tab\" id=\"title\">Google</div></div>
    <div class=\"bar\">
      <button onclick=\"pywebview.api.back()\">←</button>
      <button onclick=\"pywebview.api.forward()\">→</button>
      <button onclick=\"pywebview.api.refresh()\">↻</button>
      <div class=\"address\">
        <span id=\"secure\">🔒</span>
        <input id=\"addr\" class=\"addr\" type=\"text\" value=\"{self.HOME_URL}\" />
      </div>
      <button onclick=\"pywebview.api.bookmark()\">★</button>
      <div class=\"status\" id=\"status\">Ready</div>
    </div>
  </div>
<script>
  const addr = document.getElementById('addr');
  const title = document.getElementById('title');
  const status = document.getElementById('status');
  const secure = document.getElementById('secure');

  addr.addEventListener('keydown', function(ev) {{
    if (ev.key === 'Enter') pywebview.api.navigate(addr.value || '');
  }});

  async function pollState() {{
    try {{
      const s = await pywebview.api.get_state();
      if (s && s.url) addr.value = s.url;
      if (s && s.title) title.textContent = s.title;
      if (s && s.status) status.textContent = s.status;
      secure.textContent = (s && s.secure === '1') ? '🔒' : '⚠';
    }} catch (e) {{}}
  }}

  setInterval(pollState, 250);
  pollState();
</script>
</body>
</html>
"""


__all__ = ["BrowserWindow"]
