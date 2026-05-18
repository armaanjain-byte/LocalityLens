"""Placeholder for a future Tree-sitter TypeScript adapter."""

from __future__ import annotations

from pathlib import Path


class TypeScriptLanguageAdapter:
    """Unimplemented adapter documenting the intended language boundary."""

    extensions = frozenset({".ts", ".tsx", ".js", ".jsx"})

    def can_parse(self, path: Path) -> bool:
        return path.suffix in self.extensions
