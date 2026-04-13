"""Layout engine for render tree nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
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


class LayoutEngine:
    """Compute block and inline layout with simplified box model."""

    def __init__(self) -> None:
        """Initialize layout logger."""

        self.logger = get_logger("renderer.layout_engine")

    def layout(self, render_root: RenderNode, viewport_width: int) -> LayoutBox:
        """Generate full layout tree starting at the root node."""

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

        margin = self._to_px(style.get("margin", "0"))
        padding = self._to_px(style.get("padding", "0"))
        border = self._to_px(style.get("border-width", "0"))

        content_x = x + margin + border + padding
        current_y = y + margin + border + padding
        width = self._to_px(style.get("width", "0")) or max(0, available_width - 2 * (margin + border + padding))
        font_size = self._to_px(style.get("font-size", str(parent_font_size)), base_font_size=parent_font_size)
        if font_size <= 0:
            font_size = parent_font_size

        if node.dom_node.tag_name.lower() == "img":
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
                img_height = 180.0

            return LayoutBox(
                render_node=node,
                x=x,
                y=y,
                width=img_width + 2 * (padding + border),
                height=img_height + 2 * (padding + border),
                children=[],
            )

        box = LayoutBox(render_node=node, x=x, y=y, width=width + 2 * (padding + border), height=0)

        display = style.get("display", "block").strip().lower()
        if not node.children:
            line_height = self._to_px(style.get("line-height", "0"), base_font_size=font_size)
            content_height = line_height or (font_size * 1.4)
            box.height = content_height + 2 * (margin + border + padding)
            return box

        if display == "inline":
            child_x = content_x
            max_height = 0.0
            for child in node.children:
                child_box = self._layout_node(child, child_x, current_y, width, font_size)
                box.children.append(child_box)
                child_x += child_box.width
                max_height = max(max_height, child_box.height)
            box.height = max_height + 2 * (margin + border + padding)
        else:
            for child in node.children:
                child_box = self._layout_node(child, content_x, current_y, width, font_size)
                box.children.append(child_box)
                current_y += child_box.height
            content_height = current_y - (y + margin + border + padding)
            box.height = content_height + 2 * (margin + border + padding)

        self.logger.debug(
            "Layout node %s at (%.1f,%.1f) size (%.1f,%.1f)",
            node.dom_node.tag_name,
            box.x,
            box.y,
            box.width,
            box.height,
        )
        return box

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
        if value.endswith("px"):
            value = value[:-2]
        try:
            return float(value)
        except ValueError:
            return 0.0
