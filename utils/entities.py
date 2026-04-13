"""HTML entity decoding helpers."""

from __future__ import annotations

import html


def decode_html_entities(value: str) -> str:
    """Decode named and numeric HTML entities into display-safe text.

    Decodes common entities such as ``&nbsp;``, ``&amp;``, ``&quot;``,
    ``&lt;``, ``&gt;``, ``&#160;``, ``&#39;`` and other supported HTML entities.
    Non-breaking spaces are normalized to regular spaces for inline layout.
    """

    if not value:
        return ""
    decoded = html.unescape(value)
    return decoded.replace("\xa0", " ")
