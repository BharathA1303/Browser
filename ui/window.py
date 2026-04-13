"""Main tkinter browser window."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from engine.event_loop import EventLoop
from renderer.paint_engine import PaintEngine
from ui.address_bar import AddressBar
from ui.tab_manager import TabManager
from utils.config import CONFIG
from utils.logger import get_logger


class BrowserWindow:
    """Main window with controls, tabs and viewport."""

    def __init__(self) -> None:
        """Build the full browser UI and wire callbacks."""

        self.logger = get_logger("ui.window")
        self.root = tk.Tk()
        self.root.title("Browser v1")
        self.root.geometry(f"{CONFIG.default_window_width}x{CONFIG.default_window_height}")

        self.event_loop = EventLoop()
        self.paint_engine = PaintEngine()

        self._build_controls()
        self._build_viewport()

        self.tabs = TabManager(self.notebook)
        first_tab = self.tabs.open_tab()
        self._bind_canvas_scrolling(first_tab.canvas)

        self.root.after(20, self._pump_events)

    def _build_controls(self) -> None:
        """Create navigation controls and address bar."""

        controls = tk.Frame(self.root)
        controls.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        self.back_button = tk.Button(controls, text="←", width=4, command=self.go_back)
        self.back_button.pack(side=tk.LEFT, padx=(0, 4))

        self.forward_button = tk.Button(controls, text="→", width=4, command=self.go_forward)
        self.forward_button.pack(side=tk.LEFT, padx=(0, 4))

        self.refresh_button = tk.Button(controls, text="⟳", width=4, command=self.refresh)
        self.refresh_button.pack(side=tk.LEFT, padx=(0, 8))

        self.address_bar = AddressBar(controls)
        self.address_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.address_bar.set_on_submit(self.navigate)

    def _build_viewport(self) -> None:
        """Create tab notebook and content viewport."""

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def _pump_events(self) -> None:
        """Tick custom event loop periodically from tkinter loop."""

        self.event_loop.tick()
        self.root.after(20, self._pump_events)

    def navigate(self, url: str, record_history: bool = True) -> None:
        """Navigate current tab to a URL."""

        tab = self.tabs.current_tab()
        if not tab:
            return

        self.address_bar.set_loading(True)
        self.root.update_idletasks()

        try:
            viewport_width = max(tab.canvas.winfo_width(), 300)
            result = tab.engine.navigate(
                url,
                viewport_width=viewport_width,
                record_history=record_history,
            )
            self.paint_engine.paint(
                tab.canvas,
                result.layout_root,
                current_url=result.final_url,
                navigate_callback=self.navigate,
            )
            visible_width = max(tab.canvas.winfo_width(), viewport_width)
            visible_height = max(tab.canvas.winfo_height(), int(result.layout_root.height))
            tab.canvas.configure(scrollregion=(0, 0, visible_width, visible_height))
            tab.title = result.page_title or result.final_url
            self.notebook.tab(tab.frame, text=tab.title[:25])
            self.address_bar.set_url(result.final_url)
        except Exception as error:  # noqa: BLE001
            tab.canvas.delete("all")
            tab.canvas.create_text(20, 20, text=f"Navigation error: {error}", anchor="nw", fill="red")
            self.logger.exception("Navigation failed")
        finally:
            self.address_bar.set_loading(False)

    def go_back(self) -> None:
        """Navigate to previous history entry in current tab."""

        tab = self.tabs.current_tab()
        if not tab:
            return
        previous = tab.engine.history.back()
        if previous:
            self.navigate(previous, record_history=False)

    def go_forward(self) -> None:
        """Navigate to next history entry in current tab."""

        tab = self.tabs.current_tab()
        if not tab:
            return
        next_url = tab.engine.history.forward()
        if next_url:
            self.navigate(next_url, record_history=False)

    def refresh(self) -> None:
        """Refresh current URL."""

        current = self.address_bar.get_url()
        if current:
            self.navigate(current)

    def run(self) -> None:
        """Run the browser UI loop."""

        self.event_loop.start()
        self.root.mainloop()

    def _bind_canvas_scrolling(self, canvas: tk.Canvas) -> None:
        """Bind mouse wheel behavior for canvas scrolling."""

        def on_mousewheel(event: tk.Event[tk.Misc]) -> None:
            delta = int(-1 * (event.delta / 120))
            canvas.yview_scroll(delta, "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)
