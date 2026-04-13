"""WebView2-powered browser window orchestration."""

from __future__ import annotations

import json
from typing import Any

import webview

from storage.bookmarks import BookmarksManager
from ui.tab_manager import BrowserTab, TabManager
from utils.logger import get_logger


class _ToolbarApi:
    """JavaScript bridge API for toolbar actions."""

    def __init__(self, app: "BrowserWindow", tab_id: str) -> None:
        """Bind toolbar API methods to a tab context."""

        self._app = app
        self._tab_id = tab_id

    def navigate(self, text: str) -> None:
        """Navigate current tab from address-bar input."""

        self._app.navigate_tab(self._tab_id, text)

    def go_back(self) -> None:
        """Navigate browser history back in current tab."""

        self._app.eval_js(self._tab_id, "history.back();")

    def go_forward(self) -> None:
        """Navigate browser history forward in current tab."""

        self._app.eval_js(self._tab_id, "history.forward();")

    def refresh(self) -> None:
        """Reload the current document."""

        self._app.eval_js(self._tab_id, "location.reload();")

    def add_bookmark(self) -> None:
        """Save current tab URL and title to bookmarks."""

        self._app.add_bookmark(self._tab_id)

    def open_bookmark(self, url: str) -> None:
        """Open selected bookmark URL."""

        if url:
            self._app.navigate_tab(self._tab_id, url)

    def new_tab(self) -> None:
        """Create a new tab window."""

        self._app.create_tab()

    def switch_tab(self, tab_id: str) -> None:
        """Switch focus to another tab."""

        self._app.activate_tab(tab_id)

    def close_tab(self, tab_id: str) -> None:
        """Close a target tab."""

        self._app.close_tab(tab_id)


class BrowserWindow:
    """Main pywebview-based browser application."""

    HOME_URL = "https://www.google.com"

    def __init__(self) -> None:
        """Initialize browser window, tab manager, and persistence services."""

        self.logger = get_logger("ui.window")
        self.bookmarks = BookmarksManager()
        self.tabs = TabManager(
            on_tab_created=self._on_tab_created,
            on_tab_closed=self._on_tab_closed,
        )
        self._shutdown_requested = False
        self.create_tab(self.HOME_URL)

    def run(self) -> None:
        """Start the pywebview event loop (WebView2 on Windows)."""

        webview.start(debug=False)

    def create_tab(self, initial_url: str | None = None) -> BrowserTab:
        """Create and return a new tab window."""

        url = initial_url or self.HOME_URL
        tab_id = self.tabs.allocate_tab_id()
        api = _ToolbarApi(self, tab_id)
        tab = self.tabs.create_tab(home_url=url, js_api=api, tab_id=tab_id)

        tab.window.events.loaded += lambda: self._on_loaded(tab.tab_id)
        tab.window.events.closed += lambda: self._on_window_closed(tab.tab_id)
        return tab

    def activate_tab(self, tab_id: str) -> None:
        """Focus and show a tab window."""

        tab = self.tabs.activate_tab(tab_id)
        if tab:
            self._inject_toolbar(tab, status="Done")

    def close_tab(self, tab_id: str) -> None:
        """Close tab and exit when all tabs are closed."""

        self.tabs.close_tab(tab_id)
        if not self.tabs.list_tabs() and not self._shutdown_requested:
            self._shutdown_requested = True
            webview.stop()

    def navigate_tab(self, tab_id: str, user_input: str) -> None:
        """Navigate a tab from address-bar style input."""

        tab = self.tabs.get_tab(tab_id)
        if not tab or tab.closed:
            return

        nav = tab.engine.resolve_input(user_input)
        self._inject_toolbar(tab, status="Loading...")

        if nav.is_internal and nav.target_url == "browser://history":
            tab.window.load_html(nav.html_content)
            tab.current_url = nav.target_url
            tab.title = "Browsing History"
            tab.engine.record_visit(tab.current_url, tab.title)
            self._set_window_title(tab)
            self._inject_toolbar(tab, status="Done")
            return

        tab.window.load_url(nav.target_url)

    def add_bookmark(self, tab_id: str) -> None:
        """Add current tab page to bookmark storage."""

        tab = self.tabs.get_tab(tab_id)
        if not tab or not tab.current_url:
            return
        self.bookmarks.add(tab.current_url, tab.title or tab.current_url)
        self._inject_toolbar(tab, status="Done")

    def eval_js(self, tab_id: str, script: str) -> Any:
        """Evaluate JavaScript in a tab window safely."""

        tab = self.tabs.get_tab(tab_id)
        if not tab or tab.closed:
            return None
        try:
            return tab.window.evaluate_js(script)
        except Exception as error:  # noqa: BLE001
            self.logger.warning("evaluate_js failed on %s: %s", tab_id, error)
            return None

    def _on_tab_created(self, tab: BrowserTab) -> None:
        """Handle tab creation lifecycle hook."""

        self.logger.info("Created tab %s", tab.tab_id)

    def _on_tab_closed(self, tab_id: str) -> None:
        """Handle tab close lifecycle hook."""

        self.logger.info("Closed tab %s", tab_id)

    def _on_window_closed(self, tab_id: str) -> None:
        """Handle native window close initiated by user."""

        self.tabs.handle_window_closed(tab_id)
        if not self.tabs.list_tabs() and not self._shutdown_requested:
            self._shutdown_requested = True
            webview.stop()

    def _on_loaded(self, tab_id: str) -> None:
        """Sync URL/title after navigation and inject toolbar overlay."""

        tab = self.tabs.get_tab(tab_id)
        if not tab or tab.closed:
            return

        info = self._read_page_info(tab)
        if info["url"] and not (
            tab.current_url == "browser://history" and info["url"].startswith("about:")
        ):
            tab.current_url = info["url"]
        if info["title"]:
            tab.title = info["title"]

        if tab.current_url and tab.current_url != "about:blank":
            tab.engine.record_visit(tab.current_url, tab.title)

        self._set_window_title(tab)
        self._inject_toolbar(tab, status="Done")

    def _set_window_title(self, tab: BrowserTab) -> None:
        """Update native window title from page title."""

        title = f"{(tab.title or tab.current_url or 'New Tab')} - Browser v1"
        if hasattr(tab.window, "set_title"):
            tab.window.set_title(title)

    def _read_page_info(self, tab: BrowserTab) -> dict[str, str]:
        """Read current URL and title from page JavaScript context."""

        js = "JSON.stringify({url: location.href || '', title: document.title || ''});"
        payload = self.eval_js(tab.tab_id, js)
        if not payload:
            return {"url": tab.current_url, "title": tab.title}

        if isinstance(payload, str):
            try:
                data = json.loads(payload)
                return {
                    "url": str(data.get("url", "")),
                    "title": str(data.get("title", "")),
                }
            except json.JSONDecodeError:
                return {"url": tab.current_url, "title": tab.title}

        if isinstance(payload, dict):
            return {
                "url": str(payload.get("url", "")),
                "title": str(payload.get("title", "")),
            }

        return {"url": tab.current_url, "title": tab.title}

    def _inject_toolbar(self, tab: BrowserTab, status: str) -> None:
        """Inject floating toolbar HTML/CSS/JS into current page."""

        tabs_data = [
            {
                "id": current.tab_id,
                "title": (current.title or current.current_url or "New Tab")[:24],
                "active": current.tab_id == tab.tab_id,
            }
            for current in self.tabs.list_tabs()
        ]
        bookmarks = [
            {"title": (bookmark.title or bookmark.url)[:80], "url": bookmark.url}
            for bookmark in self.bookmarks.load()
        ]

        address = json.dumps(tab.current_url or self.HOME_URL)
        status_text = json.dumps(status)
        tabs_json = json.dumps(tabs_data)
        bookmarks_json = json.dumps(bookmarks)

        script = f"""
(function() {{
  const existing = document.getElementById('__browser_toolbar_root');
  if (existing) existing.remove();

  const root = document.createElement('div');
  root.id = '__browser_toolbar_root';
  root.style.position = 'fixed';
  root.style.top = '0';
  root.style.left = '0';
  root.style.right = '0';
  root.style.zIndex = '2147483647';
  root.style.background = '#f5f5f5';
  root.style.borderBottom = '1px solid #ccc';
  root.style.fontFamily = 'Segoe UI, Arial, sans-serif';
  root.style.padding = '6px';

  const tabs = {tabs_json};
  const bookmarks = {bookmarks_json};

  const tabRow = document.createElement('div');
  tabRow.style.display = 'flex';
  tabRow.style.gap = '6px';
  tabRow.style.marginBottom = '6px';

  tabs.forEach(function(t) {{
    const btn = document.createElement('button');
    btn.textContent = t.title;
    btn.style.padding = '3px 8px';
    btn.style.border = '1px solid #bbb';
    btn.style.background = t.active ? '#fff' : '#ececec';
    btn.onclick = function() {{ pywebview.api.switch_tab(t.id); }};

    const close = document.createElement('button');
    close.textContent = 'x';
    close.style.marginLeft = '2px';
    close.style.border = '1px solid #bbb';
    close.onclick = function() {{ pywebview.api.close_tab(t.id); }};

    const wrap = document.createElement('span');
    wrap.appendChild(btn);
    wrap.appendChild(close);
    tabRow.appendChild(wrap);
  }});

  const plus = document.createElement('button');
  plus.textContent = '+';
  plus.style.padding = '3px 8px';
  plus.onclick = function() {{ pywebview.api.new_tab(); }};
  tabRow.appendChild(plus);

  const row = document.createElement('div');
  row.style.display = 'flex';
  row.style.alignItems = 'center';
  row.style.gap = '6px';

  function mkBtn(text, action) {{
    const b = document.createElement('button');
    b.textContent = text;
    b.style.padding = '4px 8px';
    b.onclick = action;
    return b;
  }}

  row.appendChild(mkBtn('←', function() {{ pywebview.api.go_back(); }}));
  row.appendChild(mkBtn('→', function() {{ pywebview.api.go_forward(); }}));
  row.appendChild(mkBtn('⟳', function() {{ pywebview.api.refresh(); }}));
  row.appendChild(mkBtn('★', function() {{ pywebview.api.add_bookmark(); }}));

  const bm = document.createElement('select');
  bm.style.maxWidth = '220px';
  const defaultOpt = document.createElement('option');
  defaultOpt.textContent = 'Bookmarks';
  defaultOpt.value = '';
  bm.appendChild(defaultOpt);
  bookmarks.forEach(function(item) {{
    const opt = document.createElement('option');
    opt.value = item.url;
    opt.textContent = item.title;
    bm.appendChild(opt);
  }});
  bm.onchange = function() {{ if (bm.value) pywebview.api.open_bookmark(bm.value); }};
  row.appendChild(bm);

  const address = document.createElement('input');
  address.type = 'text';
  address.value = {address};
  address.style.flex = '1';
  address.style.minWidth = '220px';
  address.style.padding = '4px 8px';
  address.onkeydown = function(event) {{
    if (event.key === 'Enter') pywebview.api.navigate(address.value);
  }};
  row.appendChild(address);

  const status = document.createElement('span');
  status.textContent = {status_text};
  status.style.minWidth = '85px';
  status.style.textAlign = 'right';
  row.appendChild(status);

  root.appendChild(tabRow);
  root.appendChild(row);
  document.documentElement.style.paddingTop = '88px';
  document.body.style.paddingTop = '88px';
  document.body.appendChild(root);
}})();
"""
        self.eval_js(tab.tab_id, script)
