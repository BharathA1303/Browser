"""Tab management for independent browser engines."""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional

from engine.browser_engine import BrowserEngine


@dataclass
class BrowserTab:
    """Represents one browser tab state."""

    tab_id: str
    tab_frame: tk.Frame
    body_frame: tk.Frame
    canvas: tk.Canvas
    scrollbar_y: ttk.Scrollbar
    engine: BrowserEngine
    title: str = "New Tab"
    current_url: str = ""
    last_response_size_bytes: int | None = None
    tab_button: tk.Button | None = None
    close_button: tk.Button | None = None


class TabManager:
    """Manage opening, switching and closing tabs."""

    def __init__(
        self,
        tab_strip: tk.Frame,
        content_area: tk.Frame,
        on_tab_created: Callable[[BrowserTab], None] | None = None,
        on_tab_selected: Callable[[BrowserTab], None] | None = None,
    ) -> None:
        """Initialize tab container and internal map."""

        self.tab_strip = tab_strip
        self.content_area = content_area
        self.tabs: Dict[str, BrowserTab] = {}
        self.selected_tab_id: str | None = None
        self._tab_counter = 0
        self._on_tab_created = on_tab_created
        self._on_tab_selected = on_tab_selected
        self.plus_button = tk.Button(self.tab_strip, text="+", width=3)
        self.plus_button.pack(side=tk.RIGHT, padx=(6, 0))

    def open_tab(self, title: str = "New Tab") -> BrowserTab:
        """Create and select a new tab with independent engine."""

        self._tab_counter += 1
        tab_id = f"tab-{self._tab_counter}"

        tab_frame = tk.Frame(self.tab_strip, bd=1, relief=tk.RAISED)
        tab_frame.pack(side=tk.LEFT, padx=(0, 4), pady=(2, 0))

        body_frame = tk.Frame(self.content_area)
        canvas = tk.Canvas(body_frame, bg="white")
        scrollbar_y = ttk.Scrollbar(body_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar_y.set)

        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        label_button = tk.Button(
            tab_frame,
            text=title,
            bd=0,
            padx=10,
            pady=2,
            command=lambda tid=tab_id: self.select_tab(tid),
        )
        label_button.pack(side=tk.LEFT)

        close_button = tk.Button(
            tab_frame,
            text="×",
            bd=0,
            padx=4,
            pady=2,
            command=lambda tid=tab_id: self.close_tab(tid),
        )
        close_button.pack(side=tk.LEFT)

        tab = BrowserTab(
            tab_id=tab_id,
            tab_frame=tab_frame,
            body_frame=body_frame,
            canvas=canvas,
            scrollbar_y=scrollbar_y,
            engine=BrowserEngine(),
            title=title,
            tab_button=label_button,
            close_button=close_button,
        )
        self.tabs[tab_id] = tab
        self.plus_button.configure(command=self._open_and_select_new_tab)
        if self._on_tab_created:
            self._on_tab_created(tab)
        self.select_tab(tab_id)
        return tab

    def current_tab(self) -> Optional[BrowserTab]:
        """Return currently selected tab."""

        if self.selected_tab_id and self.selected_tab_id in self.tabs:
            return self.tabs[self.selected_tab_id]
        return next(iter(self.tabs.values()), None)

    def switch_to(self, tab_id: str) -> Optional[BrowserTab]:
        """Switch to tab by identifier."""

        return self.select_tab(tab_id)

    def select_tab(self, tab_id: str) -> Optional[BrowserTab]:
        """Show one tab body and update the selected tab state."""

        tab = self.tabs.get(tab_id)
        if not tab:
            return None

        if self.selected_tab_id and self.selected_tab_id in self.tabs:
            current = self.tabs[self.selected_tab_id]
            current.body_frame.pack_forget()
            current.tab_frame.configure(relief=tk.RAISED)

        tab.body_frame.pack(fill=tk.BOTH, expand=True)
        tab.tab_frame.configure(relief=tk.SUNKEN)
        self.selected_tab_id = tab_id
        if self._on_tab_selected:
            self._on_tab_selected(tab)
        return tab

    def close_tab(self, tab_id: str) -> None:
        """Close tab and select another remaining tab."""

        tab = self.tabs.pop(tab_id, None)
        if not tab:
            return
        if self.selected_tab_id == tab_id:
            self.selected_tab_id = None
        tab.body_frame.destroy()
        tab.tab_frame.destroy()
        if not self.tabs:
            self.open_tab()
            return

        if self.selected_tab_id is None:
            next_tab_id = next(iter(self.tabs.keys()))
            self.select_tab(next_tab_id)

    def _open_and_select_new_tab(self) -> None:
        """Open a new tab from the plus button."""

        self.open_tab()
