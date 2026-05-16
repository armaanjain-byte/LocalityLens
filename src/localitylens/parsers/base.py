"""Parser protocol and abstract base for trace file parsers with portable path hashing."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable

from localitylens.core.trace import Trace, TraceFormat


@runtime_checkable
class ParserProtocol(Protocol):
    """Structural protocol that every parser must satisfy."""

    format: TraceFormat

    def can_parse(self, path: Path) -> bool:
        """Return ``True`` when this parser can handle *path*."""
        ...

    def parse(self, path: Path) -> Trace:
        """Parse *path and return a Trace."""
        ...


class BaseParser(ABC):
    """Abstract base implementing ParserProtocol."""

    format: TraceFormat

    @abstractmethod
    def can_parse(self, path: Path) -> bool: ...

    @abstractmethod
    def parse(self, path: Path) -> Trace: ...

    def _make_trace_id(self, path: Path) -> str:
        """Derive a stable, cross-platform trace ID from the file path."""
        # Finding 6: Normalise to POSIX separators so IDs remain cross-platform portable
        posix_path = path.resolve().as_posix()
        digest = hashlib.sha1(posix_path.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
        return f"{path.stem}_{digest}"