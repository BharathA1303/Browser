"""WebView window-backed tab manager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

import webview

from engine.browser_engine import BrowserEngine


@dataclass
class BrowserTab:
    """Represents one tab backed by a pywebview window."""

    tab_id: str
    window: webview.Window
    engine: BrowserEngine
    title: str = "New Tab"
    current_url: str = ""
    closed: bool = False


class TabManager:
    """Create, track, switch, and close pywebview tabs."""

    def __init__(
        self,
        on_tab_created: Callable[[BrowserTab], None],
        on_tab_closed: Callable[[str], None],
    ) -> None:
        """Initialize tab state and callbacks."""

        self._on_tab_created = on_tab_created
        self._on_tab_closed = on_tab_closed
        self._tabs: Dict[str, BrowserTab] = {}
        self._active_tab_id: str | None = None
        self._counter = 0

    def create_tab(self, home_url: str, js_api: object, tab_id: str | None = None) -> BrowserTab:
        """Create a new WebView window tab and activate it."""

        if tab_id is None:
            tab_id = self.allocate_tab_id()
        window = webview.create_window(
            title="New Tab - Browser v1",
            url=home_url,
            js_api=js_api,
            width=1200,
            height=800,
            confirm_close=False,
        )
        tab = BrowserTab(tab_id=tab_id, window=window, engine=BrowserEngine())
        self._tabs[tab_id] = tab
        self._active_tab_id = tab_id
        self._on_tab_created(tab)
        return tab

    def allocate_tab_id(self) -> str:
        """Reserve and return a unique tab identifier."""

        self._counter += 1
        return f"tab-{self._counter}"

    def get_tab(self, tab_id: str) -> Optional[BrowserTab]:
        """Get a tab by id."""

        return self._tabs.get(tab_id)

    def active_tab(self) -> Optional[BrowserTab]:
        """Return current active tab."""

        if self._active_tab_id is None:
            return None
        return self._tabs.get(self._active_tab_id)

    def activate_tab(self, tab_id: str) -> Optional[BrowserTab]:
        """Activate and focus a specific tab."""

        tab = self._tabs.get(tab_id)
        if not tab or tab.closed:
            return None

        self._active_tab_id = tab_id
        if hasattr(tab.window, "restore"):
            tab.window.restore()
        if hasattr(tab.window, "show"):
            tab.window.show()
        if hasattr(tab.window, "bring_to_front"):
            tab.window.bring_to_front()
        return tab

    def close_tab(self, tab_id: str) -> None:
        """Close a tab window and update active tab state."""

        tab = self._tabs.get(tab_id)
        if not tab or tab.closed:
            return

        tab.closed = True
        if hasattr(tab.window, "destroy"):
            tab.window.destroy()

        self._tabs.pop(tab_id, None)
        self._on_tab_closed(tab_id)

        if self._active_tab_id == tab_id:
            self._active_tab_id = next(iter(self._tabs.keys()), None)
            if self._active_tab_id:
                self.activate_tab(self._active_tab_id)

    def handle_window_closed(self, tab_id: str) -> None:
        """Remove tab state when user closes the native window."""

        tab = self._tabs.get(tab_id)
        if not tab:
            return
        tab.closed = True
        self._tabs.pop(tab_id, None)
        self._on_tab_closed(tab_id)

        if self._active_tab_id == tab_id:
            self._active_tab_id = next(iter(self._tabs.keys()), None)

    def list_tabs(self) -> list[BrowserTab]:
        """Return all live tabs."""

        return [tab for tab in self._tabs.values() if not tab.closed]
