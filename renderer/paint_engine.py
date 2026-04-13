"""Paint layout boxes onto tkinter Canvas."""

from __future__ import annotations

import re
from typing import Callable, Optional
import tkinter as tk
import tkinter.font as tkfont

from renderer.layout_engine import LayoutBox
from utils.config import CONFIG
from utils.logger import get_logger


class PaintEngine:
    """Draw computed layout to a canvas."""

    def __init__(self) -> None:
        """Initialize paint logger."""

        self.logger = get_logger("renderer.paint_engine")
        self._link_targets: dict[int, str] = {}

    def paint(
        self,
        canvas: tk.Canvas,
        layout_root: LayoutBox,
        current_url: str = "",
        navigate_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Paint a full layout tree to the canvas."""

        self._safe_canvas_call(lambda: canvas.delete("all"), "delete all")
        self._link_targets.clear()
        body_background = self.sanitize_color(self._find_body_background(layout_root))
        if body_background:
            self._safe_canvas_call(lambda: canvas.configure(bg=body_background), "configure canvas background")
        else:
            safe_default_bg = self.sanitize_color("#ffffff")
            if safe_default_bg:
                self._safe_canvas_call(lambda: canvas.configure(bg=safe_default_bg), "configure default canvas background")
        self._paint_box(
            canvas,
            layout_root,
            current_url=current_url,
            navigate_callback=navigate_callback,
        )

        if navigate_callback:
            def on_canvas_motion(event: tk.Event[tk.Misc]) -> None:
                """Update cursor when pointer moves over a link item."""

                hit = self._link_item_at(canvas, event.x, event.y)
                if hit is not None:
                    self._safe_canvas_call(lambda: canvas.configure(cursor="hand2"), "set hand cursor")
                else:
                    self._safe_canvas_call(lambda: canvas.configure(cursor="arrow"), "set arrow cursor")

            def on_canvas_leave(_event: tk.Event[tk.Misc]) -> None:
                """Restore default cursor when pointer leaves the canvas."""

                self._safe_canvas_call(lambda: canvas.configure(cursor="arrow"), "restore arrow cursor")

            def on_canvas_click(event: tk.Event[tk.Misc]) -> None:
                """Navigate when clicking a painted link region."""

                hit = self._link_item_at(canvas, event.x, event.y)
                if hit is not None:
                    navigate_callback(self._link_targets[hit])

            self._safe_canvas_call(lambda: canvas.bind("<Motion>", on_canvas_motion), "bind motion handler")
            self._safe_canvas_call(lambda: canvas.bind("<Leave>", on_canvas_leave), "bind leave handler")
            self._safe_canvas_call(lambda: canvas.bind("<Button-1>", on_canvas_click), "bind click handler")
        self.logger.info("Paint complete")

    def _paint_box(
        self,
        canvas: tk.Canvas,
        box: LayoutBox,
        current_url: str = "",
        navigate_callback: Optional[Callable[[str], None]] = None,
        current_link_href: str = "",
    ) -> None:
        """Paint one layout box and its descendants."""

        style = box.render_node.computed_styles
        node = box.render_node.dom_node
        tag_name = node.tag_name.lower()

        if tag_name in {"style", "script"}:
            return

        if tag_name == "a":
            href = node.attributes.get("href", "").strip()
            if href:
                current_link_href = self._resolve_href(current_url, href)

        background_raw = style.get("background", style.get("background-color", ""))
        background = self.sanitize_color(background_raw)
        border_color = self.sanitize_color(style.get("border-color", "#000000"))
        border_width = self._to_px(style.get("border-width", "0"))

        # Skip unsupported background shorthand values like url(...) and gradients.
        if background and node.tag_name != "#text":
            self._safe_canvas_call(
                lambda: canvas.create_rectangle(
                    box.x,
                    box.y,
                    box.x + box.width,
                    box.y + box.height,
                    fill=background,
                    outline="",
                ),
                "draw background rectangle",
            )

        if border_width > 0 and node.tag_name != "#text":
            safe_border_color = border_color or self.sanitize_color("#000000")
            if safe_border_color:
                self._safe_canvas_call(
                    lambda: canvas.create_rectangle(
                        box.x,
                        box.y,
                        box.x + box.width,
                        box.y + box.height,
                        outline=safe_border_color,
                        width=border_width,
                    ),
                    "draw border rectangle",
                )

        if tag_name == "img":
            placeholder_fill = self.sanitize_color("#e6e6e6")
            placeholder_outline = self.sanitize_color("#b8b8b8")
            placeholder_text_color = self.sanitize_color("#444444") or self.sanitize_color("#000000")
            alt_text = node.attributes.get("alt", "image").strip() or "image"
            if placeholder_fill and placeholder_outline:
                self._safe_canvas_call(
                    lambda: canvas.create_rectangle(
                        box.x,
                        box.y,
                        box.x + box.width,
                        box.y + box.height,
                        fill=placeholder_fill,
                        outline=placeholder_outline,
                        width=1,
                    ),
                    "draw image placeholder rectangle",
                )
            if placeholder_text_color:
                self._safe_canvas_call(
                    lambda: canvas.create_text(
                        box.x + (box.width / 2),
                        box.y + (box.height / 2),
                        text=alt_text,
                        anchor="center",
                        fill=placeholder_text_color,
                        width=max(box.width - 8, 10),
                        font=(CONFIG.default_font_family, int(CONFIG.default_font_size * 0.9)),
                    ),
                    "draw image placeholder text",
                )
            return

        text_content = box.text_fragment if box.text_fragment is not None else node.text_content
        if node.tag_name == "#text" and text_content:
            if text_content.isspace():
                return
            color = self.sanitize_color(style.get("color", "#000000")) or self.sanitize_color("#000000")
            font_size = int(self._to_px(style.get("font-size", str(CONFIG.default_font_size))) or CONFIG.default_font_size)
            font_weight = "bold" if style.get("font-weight", "").strip().lower() in {"bold", "700", "800", "900"} else "normal"
            is_link = bool(current_link_href)
            text_font = tkfont.Font(
                family=CONFIG.default_font_family,
                size=font_size,
                weight=font_weight,
                underline=is_link,
            )
            item_id = self._safe_canvas_call(
                lambda: canvas.create_text(
                    box.x,
                    box.y,
                    text=text_content,
                    anchor="nw",
                    fill=color,
                    font=text_font,
                ),
                "draw text",
            )

            if is_link and navigate_callback and isinstance(item_id, int):
                resolved_href = current_link_href
                self._link_targets[item_id] = resolved_href

                def on_click(_event: tk.Event[tk.Misc], target: str = resolved_href) -> None:
                    """Navigate to the stored link target when clicked."""

                    navigate_callback(target)

                def on_enter(_event: tk.Event[tk.Misc]) -> None:
                    """Show pointer cursor when hovering over link text."""

                    self._safe_canvas_call(lambda: canvas.configure(cursor="hand2"), "set hand cursor on link enter")

                def on_leave(_event: tk.Event[tk.Misc]) -> None:
                    """Restore default cursor when leaving link text."""

                    self._safe_canvas_call(lambda: canvas.configure(cursor="arrow"), "set arrow cursor on link leave")

                self._safe_canvas_call(lambda: canvas.tag_bind(item_id, "<Button-1>", on_click), "bind link click")
                self._safe_canvas_call(lambda: canvas.tag_bind(item_id, "<Enter>", on_enter), "bind link enter")
                self._safe_canvas_call(lambda: canvas.tag_bind(item_id, "<Leave>", on_leave), "bind link leave")

        self.logger.debug("Paint call: %s", node.tag_name)
        for child in box.children:
            self._paint_box(
                canvas,
                child,
                current_url=current_url,
                navigate_callback=navigate_callback,
                current_link_href=current_link_href,
            )

    def _to_px(self, raw: str) -> float:
        """Convert pixel length string to float."""

        raw = raw.strip().lower()
        if raw.endswith("em"):
            try:
                return float(raw[:-2]) * CONFIG.default_font_size
            except ValueError:
                return 0.0
        if raw.endswith("px"):
            raw = raw[:-2]
        try:
            return float(raw)
        except ValueError:
            return 0.0

    def _find_body_background(self, layout_root: LayoutBox) -> str:
        """Find body background color from layout tree, if present."""

        queue = [layout_root]
        while queue:
            current = queue.pop(0)
            node = current.render_node.dom_node
            if node.tag_name.lower() == "body":
                style = current.render_node.computed_styles
                return style.get("background", style.get("background-color", "")).strip()
            queue.extend(current.children)
        return ""

    def _resolve_href(self, current_url: str, href: str) -> str:
        """Resolve a link target against the current page URL."""

        target = href.strip()
        if not target:
            return current_url
        if target.startswith("//") and current_url:
            scheme = current_url.split(":", 1)[0]
            return f"{scheme}:{target}"
        if "://" in target:
            return target
        if not current_url:
            return target

        scheme, rest = current_url.split("://", 1)
        authority = rest.split("/", 1)[0]
        base_path = "/"
        if "/" in rest:
            base_path = "/" + rest.split("/", 1)[1]

        path_part = base_path.split("?", 1)[0].split("#", 1)[0]
        if target.startswith("#"):
            return f"{scheme}://{authority}{path_part}{target}"
        if target.startswith("?"):
            return f"{scheme}://{authority}{path_part}{target}"
        if target.startswith("/"):
            return f"{scheme}://{authority}{target}"

        directory = path_part.rsplit("/", 1)[0]
        if not directory.startswith("/"):
            directory = f"/{directory}" if directory else ""
        if directory.endswith("/"):
            resolved_path = f"{directory}{target}"
        elif directory:
            resolved_path = f"{directory}/{target}"
        else:
            resolved_path = f"/{target}"
        return f"{scheme}://{authority}{resolved_path}"

    def _link_item_at(self, canvas: tk.Canvas, x: int, y: int) -> int | None:
        """Return the top-most link item under the given canvas coordinates."""

        for item in reversed(canvas.find_overlapping(x, y, x, y)):
            if item in self._link_targets:
                return item
        return None

    def sanitize_color(self, value: str) -> str:
        """Convert CSS color input into a safe tkinter color or empty string."""

        raw = (value or "").strip().lower()
        if not raw:
            return ""
        if raw in {"transparent", "inherit", "none"}:
            return ""
        if raw.startswith("url("):
            return ""
        if "gradient" in raw:
            return ""

        hex_match = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", raw)
        if hex_match:
            if len(raw) == 4:
                return "#" + "".join([char * 2 for char in raw[1:]])
            return raw

        rgb_match = re.fullmatch(
            r"rgba?\(\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})(?:\s*,\s*([0-9]*\.?[0-9]+))?\s*\)",
            raw,
        )
        if rgb_match:
            r_val = int(rgb_match.group(1))
            g_val = int(rgb_match.group(2))
            b_val = int(rgb_match.group(3))
            r_val = max(0, min(255, r_val))
            g_val = max(0, min(255, g_val))
            b_val = max(0, min(255, b_val))
            return f"#{r_val:02x}{g_val:02x}{b_val:02x}"

        if "," in raw:
            return ""

        return ""

    def _safe_canvas_call(self, action: Callable[[], object], context: str) -> object | None:
        """Execute a canvas call safely and log Tcl errors without crashing paint."""

        try:
            return action()
        except tk.TclError as error:
            self.logger.warning("Canvas draw skipped (%s): %s", context, error)
            return None
