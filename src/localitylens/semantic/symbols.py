"""Symbol data models for semantic analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SymbolKind(str, Enum):
    """Kinds of code symbols LocalityLens tracks."""

    FUNCTION = "function"
    CLASS = "class"
    VARIABLE = "variable"
    MODULE = "module"
    UNKNOWN = "unknown"


@dataclass
class Symbol:
    """A named code entity referenced in a trace.

    Attributes:
        name: Fully-qualified symbol name.
        kind: Category of the symbol.
        file_path: Source file that defines this symbol.
        line: Definition line number, if known.
        reference_count: How often this symbol was referenced in the trace.
    """

    name: str
    kind: SymbolKind = SymbolKind.UNKNOWN
    file_path: str = ""
    line: int | None = None
    reference_count: int = 0

    def __hash__(self) -> int:
        return hash((self.name, self.file_path))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Symbol):
            return NotImplemented
        return self.name == other.name and self.file_path == other.file_path