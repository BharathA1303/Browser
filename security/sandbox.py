"""Sandbox utilities for restricting JS access."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Set


@dataclass
class Sandbox:
    """Runtime sandbox policy for JS interpreter."""

    allowed_globals: Set[str] = field(default_factory=lambda: {"console", "Math"})

    def filter_globals(self, globals_map: Dict[str, Any]) -> Dict[str, Any]:
        """Return only allowed global names from provided map."""

        return {name: value for name, value in globals_map.items() if name in self.allowed_globals}

    def can_access(self, name: str) -> bool:
        """Check if global symbol is allowed."""

        return name in self.allowed_globals
