"""Parser protocol and abstract base for trace file parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable

from localitylens.core.trace import Trace, TraceFormat


@runtime_checkable
class ParserProtocol(Protocol):
    """Structural protocol that every parser must satisfy."""

    #: The format this parser handles.
    format: TraceFormat

    def can_parse(self, path: Path) -> bool:
        """Return ``True`` when this parser can handle *path*."""
        ...

    def parse(self, path: Path) -> Trace:
        """Parse *path* and return a :class:`~localitylens.core.trace.Trace`.

        Raises:
            ParseError: On malformed or unrecognised content.
        """
        ...


class BaseParser(ABC):
    """Abstract base implementing :class:`ParserProtocol`.

    Subclasses must set :attr:`format` and implement
    :meth:`can_parse` and :meth:`parse`.
    """

    format: TraceFormat

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Return ``True`` when this parser can handle *path*."""

    @abstractmethod
    def parse(self, path: Path) -> Trace:
        """Parse *path* and return a :class:`~localitylens.core.trace.Trace`.

        Raises:
            ParseError: On malformed or unrecognised content.
        """

    def _make_trace_id(self, path: Path) -> str:
        """Derive a stable trace ID from the file path.

        Args:
            path: Source file path.

        Returns:
            String identifier based on the file stem.
        """
        return path.stem