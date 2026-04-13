"""Main tkinter browser window."""

from __future__ import annotations

from html import escape
import tkinter as tk
from tkinter import ttk

from engine.event_loop import EventLoop
from engine.browser_engine import NavigationResult
from renderer.paint_engine import PaintEngine
from ui.address_bar import AddressBar
from ui.tab_manager import BrowserTab, TabManager
from storage.bookmarks import BookmarksManager, BookmarkEntry
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
        self.bookmarks = BookmarksManager()

        self._build_controls()
        self._build_viewport()

        self.tabs = TabManager(
            self.tab_strip,
            self.content_area,
            on_tab_created=self._bind_new_tab,
            on_tab_selected=self._on_tab_selected,
        )
        first_tab = self.tabs.open_tab()

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

        self.bookmark_button = tk.Button(controls, text="★", width=4, command=self.add_bookmark)
        self.bookmark_button.pack(side=tk.LEFT, padx=(0, 4))

        self.bookmark_menu_button = tk.Menubutton(controls, text="Bookmarks", relief=tk.RAISED, width=10)
        self.bookmark_menu = tk.Menu(self.bookmark_menu_button, tearoff=0)
        self.bookmark_menu.configure(postcommand=self._refresh_bookmarks_menu)
        self.bookmark_menu_button.configure(menu=self.bookmark_menu)
        self.bookmark_menu_button.pack(side=tk.LEFT, padx=(0, 8))

        self.address_bar = AddressBar(controls)
        self.address_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.address_bar.set_on_submit(self.navigate)

    def _build_viewport(self) -> None:
        """Create tab notebook and content viewport."""

        self.tab_strip = tk.Frame(self.root)
        self.tab_strip.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 4))

        self.content_area = tk.Frame(self.root)
        self.content_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def _on_tab_selected(self, tab: BrowserTab) -> None:
        """Sync the address bar when the active tab changes."""

        self.address_bar.set_url(tab.current_url)
        title_source = tab.title if tab.current_url else "Browser v1"
        self._update_window_title(title_source)
        if tab.last_response_size_bytes is not None:
            self.address_bar.set_done(tab.last_response_size_bytes)
        else:
            self.address_bar.set_ready()

    def _bind_new_tab(self, tab: BrowserTab) -> None:
        """Bind scroll behavior for each newly created tab."""

        self._bind_canvas_scrolling(tab.canvas)

    def _pump_events(self) -> None:
        """Tick custom event loop periodically from tkinter loop."""

        self.event_loop.tick()
        self.root.after(20, self._pump_events)

    def navigate(self, url: str, record_history: bool = True) -> None:
        """Navigate current tab to a URL."""

        tab = self.tabs.current_tab()
        if not tab:
            return

        if url.strip().lower() == "browser://history":
            self.address_bar.set_loading(True)
            self.root.update_idletasks()
            self._show_history_page()
            self.address_bar.set_loading(False)
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
            tab.current_url = result.final_url
            tab.last_response_size_bytes = result.response_size_bytes
            if tab.tab_button is not None:
                tab.tab_button.configure(text=tab.title[:25])
            self.address_bar.set_url(result.final_url)
            self.address_bar.set_done(result.response_size_bytes)
            self._update_window_title(tab.title)
        except Exception as error:  # noqa: BLE001
            tab.canvas.delete("all")
            tab.canvas.create_text(20, 20, text=f"Navigation error: {error}", anchor="nw", fill="red")
            self.logger.exception("Navigation failed")
            self.address_bar.set_error()
        finally:
            if not (url.strip().lower() == "browser://history"):
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

    def add_bookmark(self) -> None:
        """Save the current page to bookmarks."""

        tab = self.tabs.current_tab()
        if not tab or not tab.current_url:
            return
        self.bookmarks.add(tab.current_url, tab.title or tab.current_url)
        self._refresh_bookmarks_menu()

    def _refresh_bookmarks_menu(self) -> None:
        """Rebuild the bookmarks dropdown from disk."""

        self.bookmark_menu.delete(0, tk.END)
        bookmarks = self.bookmarks.load()
        if not bookmarks:
            self.bookmark_menu.add_command(label="No bookmarks yet", state=tk.DISABLED)
            return

        for bookmark in bookmarks:
            label = bookmark.title or bookmark.url
            self.bookmark_menu.add_command(
                label=label[:40],
                command=lambda target=bookmark.url: self.navigate(target),
            )

    def _show_history_page(self) -> None:
        """Render the internal browser history page."""

        tab = self.tabs.current_tab()
        if not tab:
            return

        rows = []
        for index, record in enumerate(reversed(tab.engine.history.all_records()), start=1):
            escaped_url = escape(record.url)
            timestamp = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            rows.append(
                f'<li><a href="{escaped_url}">{index}. {escaped_url}</a> '
                f'<span style="color:#666">{timestamp}</span></li>'
            )

        html_text = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Browsing History</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #fafafa; color: #222; }
    h1 { font-size: 24px; }
    ul { line-height: 1.7; }
    a { color: #0645ad; }
  </style>
</head>
<body>
  <h1>Browsing History</h1>
  <p>Click any entry to revisit that page.</p>
  <ul>
    %s
  </ul>
</body>
</html>
""" % "\n    ".join(rows or ["<li>No history yet</li>"])

        result = tab.engine.render_html(
            "browser://history",
            html_text,
            viewport_width=max(tab.canvas.winfo_width(), 300),
            page_title="Browsing History",
            record_history=False,
        )
        self._render_result(tab, result)

    def _render_result(self, tab: BrowserTab, result: NavigationResult) -> None:
        """Paint a navigation result into the current tab and update UI state."""

        self.paint_engine.paint(
            tab.canvas,
            result.layout_root,
            current_url=result.final_url,
            navigate_callback=self.navigate,
        )
        visible_width = max(tab.canvas.winfo_width(), 300)
        visible_height = max(tab.canvas.winfo_height(), int(result.layout_root.height))
        tab.canvas.configure(scrollregion=(0, 0, visible_width, visible_height))
        tab.title = result.page_title or result.final_url
        tab.current_url = result.final_url
        tab.last_response_size_bytes = result.response_size_bytes
        if tab.tab_button is not None:
            tab.tab_button.configure(text=tab.title[:25])
        self.address_bar.set_url(result.final_url)
        self.address_bar.set_done(result.response_size_bytes)
        self._update_window_title(tab.title)

    def _update_window_title(self, page_title: str) -> None:
        """Update the main window title bar with the active page title."""

        clean_title = page_title.strip() or "Browser v1"
        self.root.title(f"{clean_title} - Browser v1")

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
