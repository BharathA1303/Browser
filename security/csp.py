"""Content Security Policy validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class CSPPolicy:
    """Parsed CSP directives map."""

    directives: Dict[str, List[str]]


class CSPChecker:
    """Evaluate resource URLs against CSP directives."""

    def parse(self, header_value: str) -> CSPPolicy:
        """Parse CSP header string into directives."""

        directives: Dict[str, List[str]] = {}
        for chunk in header_value.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = chunk.split()
            key = parts[0].lower()
            values = parts[1:] if len(parts) > 1 else []
            directives[key] = values
        return CSPPolicy(directives=directives)

    def is_allowed(self, policy: CSPPolicy, resource_type: str, resource_url: str, origin: str) -> bool:
        """Return whether CSP allows loading the resource."""

        directive = f"{resource_type}-src"
        sources = policy.directives.get(directive) or policy.directives.get("default-src", ["*"])

        if "'none'" in sources:
            return False
        if "*" in sources:
            return True
        if "'self'" in sources and resource_url.startswith(origin):
            return True

        for source in sources:
            if source in {"'self'", "'none'"}:
                continue
            if resource_url.startswith(source):
                return True

        return False
