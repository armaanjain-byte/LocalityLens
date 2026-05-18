"""Python semantic extraction adapter."""

from __future__ import annotations

from pathlib import Path

from localitylens.semantic.python_ast import PythonModuleSemantics, extract_python_semantics


class PythonLanguageAdapter:
    """Adapter around the stdlib AST implementation."""

    extensions = frozenset({".py"})

    def can_parse(self, path: Path) -> bool:
        return path.suffix in self.extensions

    def parse(self, path: Path, logical_path: str | None = None) -> PythonModuleSemantics:
        return extract_python_semantics(path, logical_path=logical_path)
