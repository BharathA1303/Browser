"""Tab management for independent browser engines."""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional

from engine.browser_engine import BrowserEngine


@dataclass
class BrowserTab:
    """Represents one browser tab state."""

    tab_id: str
    frame: ttk.Frame
    canvas: tk.Canvas
    scrollbar_y: ttk.Scrollbar
    engine: BrowserEngine
    title: str = "New Tab"


class TabManager:
    """Manage opening, switching and closing tabs."""

    def __init__(self, notebook: ttk.Notebook) -> None:
        """Initialize tab container and internal map."""

        self.notebook = notebook
        self.tabs: Dict[str, BrowserTab] = {}

    def open_tab(self, title: str = "New Tab") -> BrowserTab:
        """Create and select a new tab with independent engine."""

        frame = ttk.Frame(self.notebook)
        canvas = tk.Canvas(frame, bg="white")
        scrollbar_y = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar_y.set)

        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.notebook.add(frame, text=title)
        self.notebook.select(frame)

        tab_id = str(frame)
        tab = BrowserTab(
            tab_id=tab_id,
            frame=frame,
            canvas=canvas,
            scrollbar_y=scrollbar_y,
            engine=BrowserEngine(),
            title=title,
        )
        self.tabs[tab_id] = tab
        return tab

    def current_tab(self) -> Optional[BrowserTab]:
        """Return currently selected tab."""

        selected = self.notebook.select()
        return self.tabs.get(str(selected))

    def switch_to(self, tab_id: str) -> Optional[BrowserTab]:
        """Switch to tab by identifier."""

        tab = self.tabs.get(tab_id)
        if tab:
            self.notebook.select(tab.frame)
        return tab

    def close_tab(self, tab_id: str) -> None:
        """Close tab and select another remaining tab."""

        tab = self.tabs.pop(tab_id, None)
        if not tab:
            return
        self.notebook.forget(tab.frame)
        if not self.tabs:
            self.open_tab()
