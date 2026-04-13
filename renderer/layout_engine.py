"""Layout engine for render tree nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import List

from renderer.render_tree import RenderNode
from utils.config import CONFIG
from utils.logger import get_logger


@dataclass
class LayoutBox:
    """Layout box with geometric metrics and children."""

    render_node: RenderNode
    x: float
    y: float
    width: float
    height: float
    children: List["LayoutBox"] = field(default_factory=list)
    text_fragment: str | None = None


class LayoutEngine:
    """Compute block and inline layout with simplified box model."""

    def __init__(self) -> None:
        """Initialize layout logger."""

        self.logger = get_logger("renderer.layout_engine")

    def layout(self, render_root: RenderNode, viewport_width: int) -> LayoutBox:
        """Generate full layout tree starting at the root node."""

        self._viewport_width = float(viewport_width)
        self._viewport_height = float(viewport_width) * 0.75
        root = self._layout_node(
            render_root,
            x=0,
            y=0,
            available_width=viewport_width,
            parent_font_size=float(CONFIG.default_font_size),
        )
        self.logger.info("Layout complete for viewport width=%s", viewport_width)
        return root

    def _layout_node(
        self,
        node: RenderNode,
        x: float,
        y: float,
        available_width: float,
        parent_font_size: float,
    ) -> LayoutBox:
        """Layout one node and recurse through children."""

        style = node.computed_styles
        tag = node.dom_node.tag_name.lower()
        display = self._effective_display(node)

        margin_top, margin_right, margin_bottom, margin_left = self._parse_box_sides(
            style.get("margin", "0"),
            base_font_size=parent_font_size,
        )
        margin_bottom_override = self._to_px(style.get("margin-bottom", "0"), base_font_size=parent_font_size)
        if margin_bottom_override > 0:
            margin_bottom = margin_bottom_override
        if tag == "p" and margin_bottom <= 0:
            margin_bottom = parent_font_size * 0.9
        padding = self._to_px(style.get("padding", "0"))
        border = self._to_px(style.get("border-width", "0"))

        width = self._to_px(style.get("width", "0"), base_font_size=parent_font_size)
        width_explicit = width > 0
        if not width_explicit:
            width = max(
                0,
                available_width
                - ((margin_left or 0.0) + (margin_right or 0.0))
                - 2 * (border + padding),
            )

        left_value = 0.0 if margin_left is None else margin_left
        right_value = 0.0 if margin_right is None else margin_right
        if width_explicit and (margin_left is None or margin_right is None):
            remaining = max(0.0, available_width - width - 2 * (border + padding) - left_value - right_value)
            if margin_left is None and margin_right is None:
                left_value = remaining / 2
                right_value = remaining / 2
            elif margin_left is None:
                left_value = remaining
            elif margin_right is None:
                right_value = remaining

        box_x = x + left_value
        box_y = y + margin_top
        content_x = box_x + border + padding
        current_y = box_y + border + padding
        font_size = self._to_px(style.get("font-size", str(parent_font_size)), base_font_size=parent_font_size)
        if font_size <= 0:
            font_size = parent_font_size

        line_height = self._to_px(style.get("line-height", "0"), base_font_size=font_size) or (font_size * 1.4)

        if display == "inline-block" or tag in {"img", "button", "input"}:
            img_width = self._to_px(style.get("width", "0"))
            img_height = self._to_px(style.get("height", "0"))
            attr_width = node.dom_node.attributes.get("width", "").strip()
            attr_height = node.dom_node.attributes.get("height", "").strip()

            if img_width <= 0 and attr_width.isdigit():
                img_width = float(attr_width)
            if img_height <= 0 and attr_height.isdigit():
                img_height = float(attr_height)

            if img_width <= 0:
                img_width = min(300.0, available_width)
            if img_height <= 0:
                img_height = line_height if tag in {"button", "input"} else 180.0

            return LayoutBox(
                render_node=node,
                x=box_x,
                y=box_y,
                width=img_width + 2 * (padding + border),
                height=img_height + 2 * (padding + border) + margin_top + margin_bottom,
                children=[],
            )

        box = LayoutBox(
            render_node=node,
            x=box_x,
            y=box_y,
            width=width + 2 * (padding + border),
            height=0,
        )

        if tag == "#text":
            text = node.dom_node.text_content or ""
            text_width = self._estimate_text_width(text, font_size)
            return LayoutBox(
                render_node=node,
                x=x,
                y=y,
                width=max(text_width, 0.0),
                height=line_height,
                children=[],
                text_fragment=text,
            )

        if not node.children:
            box.height = line_height + 2 * (border + padding) + margin_top + margin_bottom
            return box

        if self._should_use_inline_flow(node):
            inline_children, inline_content_height = self._layout_inline_flow(
                node=node,
                content_x=content_x,
                content_y=current_y,
                content_width=width,
                parent_font_size=font_size,
            )
            box.children.extend(inline_children)
            box.height = inline_content_height + 2 * (border + padding) + margin_top + margin_bottom
        else:
            for child in node.children:
                child_box = self._layout_node(
                    child,
                    content_x,
                    current_y,
                    width,
                    font_size,
                )
                box.children.append(child_box)
                current_y += child_box.height
            content_height = current_y - (box_y + border + padding)
            box.height = content_height + 2 * (border + padding) + margin_top + margin_bottom

        self.logger.debug(
            "Layout node %s at (%.1f,%.1f) size (%.1f,%.1f)",
            node.dom_node.tag_name,
            box.x,
            box.y,
            box.width,
            box.height,
        )
        return box

    def _parse_box_sides(self, raw: str, base_font_size: float) -> tuple[float, float | None, float, float | None]:
        """Parse CSS shorthand box sides (top, right, bottom, left)."""

        tokens = [token for token in raw.strip().split() if token]
        if not tokens:
            return 0.0, 0.0, 0.0, 0.0

        values: list[float | None] = []
        for token in tokens:
            if token.lower() == "auto":
                values.append(None)
            else:
                values.append(self._to_px(token, base_font_size=base_font_size))

        if len(values) == 1:
            top = right = bottom = left = values[0]
        elif len(values) == 2:
            top, right = values
            bottom = top
            left = right
        elif len(values) == 3:
            top, right, bottom = values
            left = right
        else:
            top, right, bottom, left = values[:4]

        return (
            0.0 if top is None else top,
            right,
            0.0 if bottom is None else bottom,
            left,
        )

    def _should_use_inline_flow(self, node: RenderNode) -> bool:
        """Return True if node children should be laid out in a line-box flow."""

        if not node.children:
            return False
        for child in node.children:
            child_display = self._effective_display(child)
            if child_display not in {"inline", "inline-block"}:
                return False
        return True

    def _layout_inline_flow(
        self,
        node: RenderNode,
        content_x: float,
        content_y: float,
        content_width: float,
        parent_font_size: float,
    ) -> tuple[List[LayoutBox], float]:
        """Layout inline and inline-block descendants into wrapped line boxes."""

        placed: List[LayoutBox] = []
        cursor_x = content_x
        line_top = content_y
        line_height = parent_font_size * 1.4
        used_any = False

        def new_line() -> None:
            nonlocal cursor_x, line_top, line_height
            cursor_x = content_x
            line_top += line_height
            line_height = parent_font_size * 1.4

        def place_word(text_node: RenderNode, word: str, font_size: float, word_height: float) -> None:
            nonlocal cursor_x, line_top, line_height, used_any
            word_width = self._estimate_text_width(word, font_size)
            if word_width <= 0:
                return
            if cursor_x > content_x and (cursor_x + word_width) > (content_x + content_width):
                new_line()
            placed.append(
                LayoutBox(
                    render_node=text_node,
                    x=cursor_x,
                    y=line_top,
                    width=word_width,
                    height=word_height,
                    children=[],
                    text_fragment=word,
                )
            )
            cursor_x += word_width
            line_height = max(line_height, word_height)
            used_any = True

        def consume_inline(render_node: RenderNode, inherited_font_size: float) -> None:
            nonlocal cursor_x, line_top, line_height, used_any

            style = render_node.computed_styles
            current_font_size = self._to_px(
                style.get("font-size", str(inherited_font_size)),
                base_font_size=inherited_font_size,
            ) or inherited_font_size
            current_line_height = self._to_px(
                style.get("line-height", "0"),
                base_font_size=current_font_size,
            ) or (current_font_size * 1.4)
            line_height = max(line_height, current_line_height)

            display = self._effective_display(render_node)
            tag = render_node.dom_node.tag_name.lower()

            if display == "inline-block" or tag in {"img", "button", "input"}:
                inline_block = self._layout_node(
                    render_node,
                    x=0,
                    y=0,
                    available_width=content_width,
                    parent_font_size=current_font_size,
                )
                if cursor_x > content_x and (cursor_x + inline_block.width) > (content_x + content_width):
                    new_line()
                inline_block.x = cursor_x
                inline_block.y = line_top
                placed.append(inline_block)
                cursor_x += inline_block.width
                line_height = max(line_height, inline_block.height)
                used_any = True
                return

            if tag == "#text":
                raw_text = render_node.dom_node.text_content or ""
                if not raw_text:
                    return
                tokens = re.findall(r"\S+|\s+", raw_text)
                for token in tokens:
                    if token.isspace():
                        if not used_any:
                            continue
                        space_width = self._estimate_text_width(" ", current_font_size)
                        if cursor_x > content_x and (cursor_x + space_width) > (content_x + content_width):
                            new_line()
                        else:
                            cursor_x += space_width
                        continue
                    place_word(render_node, token, current_font_size, current_line_height)
                return

            for child in render_node.children:
                if self._effective_display(child) == "block":
                    if used_any:
                        new_line()
                    block_box = self._layout_node(
                        child,
                        content_x,
                        line_top,
                        content_width,
                        current_font_size,
                    )
                    placed.append(block_box)
                    line_top += block_box.height
                    cursor_x = content_x
                    line_height = current_font_size * 1.4
                    used_any = False
                    continue
                consume_inline(child, current_font_size)

        for child in node.children:
            consume_inline(child, parent_font_size)

        total_height = (line_top - content_y) + (line_height if placed else (parent_font_size * 1.4))
        return placed, total_height

    def _effective_display(self, node: RenderNode) -> str:
        """Resolve effective display class for layout behavior."""

        style_display = node.computed_styles.get("display", "").strip().lower()
        if style_display:
            if style_display in {"inline", "block", "inline-block", "none"}:
                return style_display
            if style_display.startswith("inline"):
                return "inline"
            if style_display.startswith("block"):
                return "block"

        tag = node.dom_node.tag_name.lower()
        block_tags = {
            "document",
            "html",
            "body",
            "div",
            "p",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "ul",
            "ol",
            "li",
            "table",
            "tr",
            "header",
            "footer",
            "nav",
            "section",
            "article",
            "main",
            "td",
            "th",
        }
        inline_tags = {
            "span",
            "a",
            "strong",
            "em",
            "b",
            "i",
            "code",
            "small",
            "label",
            "#text",
        }
        inline_block_tags = {"img", "button", "input"}

        if tag in inline_block_tags:
            return "inline-block"
        if tag in inline_tags:
            return "inline"
        if tag in block_tags:
            return "block"
        return "inline"

    def _estimate_text_width(self, text: str, font_size: float) -> float:
        """Estimate text width for wrapping decisions."""

        if not text:
            return 0.0
        return max(len(text) * font_size * 0.56, font_size * 0.33)

    def _to_px(self, raw: str, base_font_size: float = 16.0) -> float:
        """Convert CSS lengths to pixel float."""

        value = raw.strip().lower()
        if not value:
            return 0.0
        if value.endswith("em"):
            try:
                return float(value[:-2]) * base_font_size
            except ValueError:
                return 0.0
        if value.endswith("rem"):
            try:
                return float(value[:-3]) * float(CONFIG.default_font_size)
            except ValueError:
                return 0.0
        if value.endswith("vw"):
            try:
                return (float(value[:-2]) / 100.0) * getattr(self, "_viewport_width", 0.0)
            except ValueError:
                return 0.0
        if value.endswith("vh"):
            try:
                return (float(value[:-2]) / 100.0) * getattr(self, "_viewport_height", 0.0)
            except ValueError:
                return 0.0
        if value.endswith("px"):
            value = value[:-2]
        try:
            return float(value)
        except ValueError:
            return 0.0
