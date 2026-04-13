"""DOM tree structures and query APIs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


@dataclass
class DOMNode:
    """Base DOM node."""

    tag_name: str
    attributes: Dict[str, str] = field(default_factory=dict)
    children: List["DOMNode"] = field(default_factory=list)
    parent: Optional["DOMNode"] = None
    text_content: str = ""

    def appendChild(self, child: "DOMNode") -> None:
        """Append a child node and set parent reference."""

        child.parent = self
        self.children.append(child)

    def removeChild(self, child: "DOMNode") -> None:
        """Remove a child if present."""

        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def querySelector(self, selector: str) -> Optional["DOMNode"]:
        """Return the first matching node for selector."""

        matches = self.querySelectorAll(selector)
        return matches[0] if matches else None

    def querySelectorAll(self, selector: str) -> List["DOMNode"]:
        """Return all matching nodes for basic CSS selector."""

        selector = selector.strip()
        if not selector:
            return []

        def matcher(node: DOMNode) -> bool:
            if selector.startswith("#"):
                return node.attributes.get("id", "") == selector[1:]
            if selector.startswith("."):
                classes = node.attributes.get("class", "").split()
                return selector[1:] in classes
            return node.tag_name.lower() == selector.lower()

        return [node for node in self._walk() if matcher(node)]

    def getElementById(self, element_id: str) -> Optional["DOMNode"]:
        """Return first node with matching id."""

        return next((node for node in self._walk() if node.attributes.get("id") == element_id), None)

    def getElementsByTagName(self, tag_name: str) -> List["DOMNode"]:
        """Return all elements matching tag name."""

        tag_name = tag_name.lower()
        if tag_name == "*":
            return [node for node in self._walk() if node.tag_name != "#text"]
        return [node for node in self._walk() if node.tag_name.lower() == tag_name]

    def _walk(self) -> Iterable["DOMNode"]:
        """Yield this node and all descendants depth-first."""

        yield self
        for child in self.children:
            yield from child._walk()


@dataclass
class DOMElement(DOMNode):
    """DOM element node."""


@dataclass
class DOMText(DOMNode):
    """DOM text node."""

    def __init__(self, text: str) -> None:
        """Create a text node."""

        super().__init__(tag_name="#text", text_content=text)
