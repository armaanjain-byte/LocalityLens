"""Placeholder for a future Tree-sitter Go adapter."""

from __future__ import annotations

from pathlib import Path


class GoLanguageAdapter:
    """Unimplemented adapter documenting the intended language boundary."""

    extensions = frozenset({".go"})

    def can_parse(self, path: Path) -> bool:
        return path.suffix in self.extensions
