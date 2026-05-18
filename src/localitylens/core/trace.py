"""Core trace data models with strict timezone normalisation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EventKind(str, Enum):
    """Taxonomy of events that can appear in a coding-agent trace."""

    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    SYMBOL_LOOKUP = "symbol_lookup"
    TOOL_CALL = "tool_call"
    LLM_TURN = "llm_turn"
    SHELL_CMD = "shell_cmd"
    UNKNOWN = "unknown"


class TraceFormat(str, Enum):
    """Supported input formats for trace files."""

    CLAUDE_CODE = "claude_code"
    GENERIC_JSON = "generic_json"


@dataclass
class TraceEvent:
    """A single event within a coding-agent trace."""

    kind: EventKind
    timestamp: Optional[datetime]   # Optional so parsers can pass None safely
    target: str
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    sequence: int = 0

    def __post_init__(self) -> None:
        # Normalise naive (or missing) timestamps to UTC so time arithmetic never raises TypeError.
        # None timestamps are replaced with the epoch sentinel — parsers that have no timestamp
        # should use _parse_ts() which already returns the epoch, but we guard here too.
        if self.timestamp is None:
            self.timestamp = datetime(1970, 1, 1, tzinfo=timezone.utc)
        elif self.timestamp.tzinfo is None:
            # Plain assignment — TraceEvent is NOT frozen, object.__setattr__ is misleading here
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)

        if not self.target:
            raise ValueError("TraceEvent.target must not be empty")
        if self.sequence < 0:
            raise ValueError(f"TraceEvent.sequence must be >= 0, got {self.sequence}")


@dataclass
class Trace:
    """Full coding-agent trace loaded from a single source file."""

    trace_id: str
    source: str
    format: TraceFormat
    events: list[TraceEvent] = field(default_factory=list)
    agent: Optional[str] = None

    @property
    def started_at(self) -> Optional[datetime]:
        """Timestamp of the first event (computed, never stale)."""
        return self.events[0].timestamp if self.events else None

    @property
    def ended_at(self) -> Optional[datetime]:
        """Timestamp of the last event (computed, never stale)."""
        return self.events[-1].timestamp if self.events else None

    def append_event(self, event: TraceEvent) -> None:
        """Append an event while preserving live boundaries."""
        self.events.append(event)