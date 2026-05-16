"""Parser protocol and abstract base with unique path hashing handles."""

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

    def can_parse(self, path: Path) -> bool: ...
    def parse(self, path: Path) -> Trace: ...


class BaseParser(ABC):
    """Abstract base implementing ParserProtocol."""

    format: TraceFormat

    @abstractmethod
    def can_parse(self, path: Path) -> bool: ...

    @abstractmethod
    def parse(self, path: Path) -> Trace: ...

    def _make_trace_id(self, path: Path) -> str:
        """Derive a collision-resistant trace ID using absolute file path digests."""
        # H-5: Block collisions between traces sharing duplicate base filenames
        abs_path = str(path.resolve())
        digest = hashlib.sha1(abs_path.encode(), usedforsecurity=False).hexdigest()[:8]
        return f"{path.stem}_{digest}"