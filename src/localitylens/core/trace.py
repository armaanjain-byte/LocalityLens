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
    timestamp: datetime
    target: str
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    sequence: int = 0

    def __post_init__(self) -> None:
        # C-2: Normalise naive timestamps to UTC so arithmetic never raises TypeError
        if self.timestamp is not None:
            if self.timestamp.tzinfo is None:
                object.__setattr__(
                    self, "timestamp",
                    self.timestamp.replace(tzinfo=timezone.utc)
                )
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

    # M-4: Use computed properties to ensure started_at/ended_at never go stale
    @property
    def started_at(self) -> Optional[datetime]:
        """Dynamically fetch the timestamp of the first event."""
        return self.events[0].timestamp if self.events else None

    @property
    def ended_at(self) -> Optional[datetime]:
        """Dynamically fetch the timestamp of the last event."""
        return self.events[-1].timestamp if self.events else None

    def append_event(self, event: TraceEvent) -> None:
        """Append an event while preserving live boundaries."""
        self.events.append(event)