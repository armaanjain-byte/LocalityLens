"""Placeholder for a future Tree-sitter Rust adapter."""

from __future__ import annotations

from pathlib import Path


class RustLanguageAdapter:
    """Unimplemented adapter documenting the intended language boundary."""

    extensions = frozenset({".rs"})

    def can_parse(self, path: Path) -> bool:
        return path.suffix in self.extensions
