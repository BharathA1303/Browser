"""Render tree builder from DOM + CSS rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from parser.css_parser import CSSParser, CSSRule
from parser.dom_tree import DOMNode
from utils.config import CONFIG
from utils.logger import get_logger


@dataclass
class RenderNode:
    """Node used by rendering and layout stages."""

    dom_node: DOMNode
    computed_styles: Dict[str, str]
    children: List["RenderNode"] = field(default_factory=list)


class RenderTreeBuilder:
    """Build render tree with cascade, specificity and inheritance."""

    def __init__(self, css_parser: CSSParser | None = None) -> None:
        """Initialize builder dependencies."""

        self.css_parser = css_parser or CSSParser()
        self.logger = get_logger("renderer.render_tree")
        self._never_render_tags = {"style", "script"}

    def build(self, dom_root: DOMNode, css_rules: List[CSSRule]) -> RenderNode:
        """Build a render tree from DOM root and parsed CSS rules."""

        render_root = self._build_node(dom_root, css_rules, parent_styles={})
        self.logger.info("Render tree built")
        return render_root

    def _build_node(
        self,
        dom_node: DOMNode,
        rules: List[CSSRule],
        parent_styles: Dict[str, str],
    ) -> RenderNode:
        """Recursively create render nodes while skipping display:none."""

        own_styles = self._compute_styles(dom_node, rules)
        computed = self.css_parser.apply_inheritance(parent_styles, own_styles)

        if dom_node.tag_name.lower() in self._never_render_tags:
            return RenderNode(dom_node=dom_node, computed_styles={"display": "none"}, children=[])

        if computed.get("display", "").strip().lower() == "none":
            return RenderNode(dom_node=dom_node, computed_styles={"display": "none"}, children=[])

        render_node = RenderNode(dom_node=dom_node, computed_styles=computed)
        for child in dom_node.children:
            child_render = self._build_node(child, rules, computed)
            if child_render.computed_styles.get("display") == "none":
                continue
            render_node.children.append(child_render)
        return render_node

    def _compute_styles(self, node: DOMNode, rules: List[CSSRule]) -> Dict[str, str]:
        """Compute final styles for one DOM node by CSS cascade order."""

        matched: list[tuple[tuple[int, int, int], int, Dict[str, str]]] = []
        for index, rule in enumerate(rules):
            if self.css_parser.match_selector(rule.selector, node):
                matched.append((rule.specificity, index, rule.declarations))

        # Sort by specificity, then source order.
        matched.sort(key=lambda item: (item[0], item[1]))

        styles: Dict[str, str] = self._default_styles_for_node(node)
        for _, _, declarations in matched:
            styles.update(declarations)

        inline_style = node.attributes.get("style", "")
        if inline_style:
            for entry in inline_style.split(";"):
                if ":" not in entry:
                    continue
                key, value = entry.split(":", 1)
                styles[key.strip().lower()] = value.strip()

        return styles

    def _default_styles_for_node(self, node: DOMNode) -> Dict[str, str]:
        """Return minimal browser default styles for common tags."""

        defaults: Dict[str, str] = {
            "font-size": f"{CONFIG.default_font_size}px",
            "font-weight": "normal",
            "color": "black",
        }

        tag = node.tag_name.lower()
        if tag in {"document", "html", "body", "div", "p", "h1", "h2", "h3", "ul", "ol", "li"}:
            defaults["display"] = "block"
        else:
            defaults["display"] = "inline"

        if tag == "h1":
            defaults["font-size"] = "2em"
            defaults["font-weight"] = "bold"
        elif tag == "h2":
            defaults["font-size"] = "1.5em"
            defaults["font-weight"] = "bold"
        elif tag == "h3":
            defaults["font-size"] = "1.17em"
            defaults["font-weight"] = "bold"
        elif tag == "a":
            defaults["color"] = "#0000EE"

        return defaults
