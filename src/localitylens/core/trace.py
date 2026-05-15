"""Core trace data models.

A *trace* is the full record of a single coding-agent session.
It contains an ordered sequence of :class:`TraceEvent` objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
    """A single event within a coding-agent trace.

    Attributes:
        kind: Semantic category of the event.
        timestamp: When the event occurred (UTC).
        target: Primary resource touched (file path, symbol name, etc.).
        metadata: Arbitrary extra data captured by the parser.
        duration_ms: How long the event took, when available.
        sequence: Zero-based position within the trace.
    """

    kind: EventKind
    timestamp: datetime
    target: str
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    sequence: int = 0


@dataclass
class Trace:
    """Full coding-agent trace loaded from a single source file.

    Attributes:
        trace_id: Unique identifier (usually derived from the source path).
        source: Path or URI the trace was loaded from.
        format: Detected input format.
        events: Ordered list of :class:`TraceEvent` objects.
        agent: Name of the agent that produced the trace, if known.
        started_at: Timestamp of the first event.
        ended_at: Timestamp of the last event.
    """

    trace_id: str
    source: str
    format: TraceFormat
    events: list[TraceEvent] = field(default_factory=list)
    agent: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.events:
            self.started_at = self.events[0].timestamp
            self.ended_at = self.events[-1].timestamp