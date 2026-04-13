"""Address bar widget."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional


class AddressBar(tk.Frame):
    """URL input control with enter-triggered navigation and loading state."""

    def __init__(self, master: tk.Misc) -> None:
        """Initialize address bar UI."""

        super().__init__(master)
        self._submit_callback: Optional[Callable[[str], None]] = None

        self._status = tk.StringVar(value="Ready")
        self._url = tk.StringVar(value="")

        self.entry = tk.Entry(self, textvariable=self._url)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self._on_enter)

        self.status_label = tk.Label(self, textvariable=self._status, width=12, anchor="w")
        self.status_label.pack(side=tk.RIGHT)

    def set_on_submit(self, callback: Callable[[str], None]) -> None:
        """Set callback executed when Enter is pressed."""

        self._submit_callback = callback

    def _on_enter(self, _event: tk.Event[tk.Misc]) -> None:
        """Submit URL to callback."""

        if self._submit_callback:
            self._submit_callback(self.get_url())

    def get_url(self) -> str:
        """Return current URL text."""

        return self._url.get().strip()

    def set_url(self, url: str) -> None:
        """Set address bar URL text."""

        self._url.set(url)

    def set_loading(self, loading: bool) -> None:
        """Update loading state label and entry enablement."""

        self._status.set("Loading..." if loading else "Ready")
