"""CSS parser with specificity and inheritance support."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, List, Tuple

from parser.dom_tree import DOMNode
from utils.logger import get_logger

Specificity = Tuple[int, int, int]


@dataclass
class CSSRule:
    """Represents one CSS rule set."""

    selector: str
    declarations: Dict[str, str] = field(default_factory=dict)
    specificity: Specificity = (0, 0, 0)


class CSSParser:
    """Parse CSS text into rule objects and selector helpers."""

    INHERITED_PROPERTIES = {"font-size", "color", "font-family"}

    def __init__(self) -> None:
        """Initialize parser logger."""

        self.logger = get_logger("parser.css_parser")

    def parse(self, css_text: str) -> List[CSSRule]:
        """Parse CSS into rules with computed specificity."""

        rules: List[CSSRule] = []
        cleaned = re.sub(r"/\*.*?\*/", "", css_text, flags=re.S)
        for selector_group, body in re.findall(r"([^{}]+)\{([^{}]+)\}", cleaned):
            declarations = self._parse_declarations(body)
            for selector in [part.strip() for part in selector_group.split(",") if part.strip()]:
                rules.append(
                    CSSRule(
                        selector=selector,
                        declarations=declarations.copy(),
                        specificity=self.calculate_specificity(selector),
                    )
                )

        self.logger.info("CSS parsed: %s rules", len(rules))
        return rules

    def _parse_declarations(self, body: str) -> Dict[str, str]:
        """Parse CSS declarations from a rule body."""

        declarations: Dict[str, str] = {}
        for entry in body.split(";"):
            if ":" not in entry:
                continue
            prop, value = entry.split(":", 1)
            declarations[prop.strip().lower()] = value.strip()
        return declarations

    def calculate_specificity(self, selector: str) -> Specificity:
        """Calculate CSS selector specificity tuple."""

        ids = len(re.findall(r"#[\w-]+", selector))
        classes = len(re.findall(r"\.[\w-]+", selector))
        stripped = re.sub(r"#[\w-]+|\.[\w-]+", " ", selector)
        tags = len([tok for tok in re.split(r"\s+|>", stripped) if tok and tok != "*"])
        return (ids, classes, tags)

    def match_selector(self, selector: str, node: DOMNode) -> bool:
        """Match simple selectors with descendant and child combinators."""

        selector = selector.strip()
        if not selector or node.tag_name == "#text":
            return False

        if ">" in selector:
            parent_selector, child_selector = [part.strip() for part in selector.split(">", 1)]
            if not self._match_simple(child_selector, node):
                return False
            return bool(node.parent and self._match_simple(parent_selector, node.parent))

        parts = [part for part in selector.split() if part]
        current: DOMNode | None = node
        for part in reversed(parts):
            while current and not self._match_simple(part, current):
                current = current.parent
            if current is None:
                return False
            current = current.parent
        return True

    def _match_simple(self, selector: str, node: DOMNode) -> bool:
        """Match tag/id/class selector segment against one node."""

        if selector == "*":
            return True

        tag_match = re.match(r"^[a-zA-Z][\w-]*", selector)
        if tag_match and node.tag_name.lower() != tag_match.group(0).lower():
            return False

        for id_value in re.findall(r"#([\w-]+)", selector):
            if node.attributes.get("id") != id_value:
                return False

        classes = node.attributes.get("class", "").split()
        for class_name in re.findall(r"\.([\w-]+)", selector):
            if class_name not in classes:
                return False

        return True

    def apply_inheritance(
        self,
        parent_styles: Dict[str, str],
        own_styles: Dict[str, str],
    ) -> Dict[str, str]:
        """Return style map with inheritable properties copied from parent."""

        merged = own_styles.copy()
        for prop in self.INHERITED_PROPERTIES:
            if prop not in merged and prop in parent_styles:
                merged[prop] = parent_styles[prop]
        return merged
