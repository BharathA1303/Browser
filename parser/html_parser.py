"""HTML tokenizer and parser implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, List

from parser.dom_tree import DOMElement, DOMNode, DOMText
from utils.logger import get_logger


@dataclass
class HTMLToken:
    """Represents a token emitted by the HTML tokenizer."""

    token_type: str
    value: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)


class HTMLTokenizer:
    """Naive but robust HTML tokenizer."""

    def __init__(self) -> None:
        """Initialize tokenizer state."""

        self.logger = get_logger("parser.html_tokenizer")

    def tokenize(self, html: str) -> List[HTMLToken]:
        """Convert an HTML string into a token stream."""

        tokens: List[HTMLToken] = []
        index = 0
        while index < len(html):
            if html.startswith("<!--", index):
                end = html.find("-->", index + 4)
                if end == -1:
                    comment_text = html[index + 4 :]
                    index = len(html)
                else:
                    comment_text = html[index + 4 : end]
                    index = end + 3
                tokens.append(HTMLToken("Comment", comment_text))
                continue

            if html.startswith("<!DOCTYPE", index) or html.startswith("<!doctype", index):
                end = html.find(">", index)
                if end == -1:
                    end = len(html) - 1
                tokens.append(HTMLToken("DOCTYPE", html[index + 2 : end].strip()))
                index = end + 1
                continue

            if html[index] == "<":
                end = html.find(">", index)
                if end == -1:
                    tokens.append(HTMLToken("Text", html[index:]))
                    break
                raw_tag = html[index + 1 : end].strip()
                index = end + 1

                if not raw_tag:
                    continue

                if raw_tag.startswith("/"):
                    tokens.append(HTMLToken("EndTag", raw_tag[1:].strip().lower()))
                    continue

                self_closing = raw_tag.endswith("/")
                if self_closing:
                    raw_tag = raw_tag[:-1].strip()

                tag_name, attributes = self._parse_tag(raw_tag)
                token_type = "SelfClosingTag" if self_closing else "StartTag"
                tokens.append(HTMLToken(token_type, tag_name.lower(), attributes))
                continue

            next_lt = html.find("<", index)
            if next_lt == -1:
                next_lt = len(html)
            text = html[index:next_lt]
            if text.strip():
                tokens.append(HTMLToken("Text", text))
            index = next_lt

        self.logger.info("HTML tokenized: %s tokens", len(tokens))
        return tokens

    def _parse_tag(self, raw_tag: str) -> tuple[str, Dict[str, str]]:
        """Parse a tag and attribute map from raw tag contents."""

        parts = raw_tag.split(maxsplit=1)
        tag_name = parts[0]
        attributes: Dict[str, str] = {}
        if len(parts) == 1:
            return tag_name, attributes

        attr_text = parts[1]
        for match in re.finditer(
            r"([a-zA-Z_:][\w:.-]*)(?:\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s\"'>]+))?",
            attr_text,
        ):
            key = match.group(1)
            value = match.group(2) or ""
            if value.startswith(("\"", "'")) and value.endswith(("\"", "'")):
                value = value[1:-1]
            attributes[key] = value
        return tag_name, attributes


class HTMLParser:
    """Build a DOM tree from HTML tokens with fault tolerance."""

    _VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        """Initialize parser with tokenizer and logger."""

        self.tokenizer = HTMLTokenizer()
        self.logger = get_logger("parser.html_parser")
        self.extracted_style_blocks: List[str] = []

    def parse(self, html: str) -> DOMElement:
        """Parse HTML into a DOM root element."""

        root = DOMElement(tag_name="document")
        stack: List[DOMElement] = [root]
        self.extracted_style_blocks = []

        for token in self.tokenizer.tokenize(html):
            if token.token_type == "DOCTYPE":
                continue

            if token.token_type == "Comment":
                continue

            if token.token_type == "Text":
                parent_tag = stack[-1].tag_name.lower()
                # Keep style/script text out of visible DOM nodes.
                if parent_tag == "style":
                    cleaned = token.value.strip()
                    if cleaned:
                        self.extracted_style_blocks.append(cleaned)
                    continue
                if parent_tag == "script":
                    continue
                text_node = DOMText(token.value)
                stack[-1].appendChild(text_node)
                continue

            if token.token_type == "StartTag":
                element = DOMElement(tag_name=token.value, attributes=token.attributes)
                stack[-1].appendChild(element)
                if token.value not in self._VOID_TAGS:
                    stack.append(element)
                continue

            if token.token_type == "SelfClosingTag":
                element = DOMElement(tag_name=token.value, attributes=token.attributes)
                stack[-1].appendChild(element)
                continue

            if token.token_type == "EndTag":
                # Fault tolerant close: pop until matching open tag or root.
                for idx in range(len(stack) - 1, 0, -1):
                    if stack[idx].tag_name == token.value:
                        del stack[idx:]
                        break

        self.logger.info("HTML parsed into DOM with %s top-level nodes", len(root.children))
        return root
