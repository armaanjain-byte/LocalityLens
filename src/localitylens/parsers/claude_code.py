"""Parser for Claude Code agent traces (newline-delimited JSON)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from localitylens.core.exceptions import ParseError
from localitylens.core.trace import EventKind, Trace, TraceEvent, TraceFormat
from localitylens.parsers.base import BaseParser
from localitylens.utils.logger import get_logger

log = get_logger(__name__)

# Mapping from Claude Code tool names to our EventKind taxonomy.
_TOOL_KIND_MAP: dict[str, EventKind] = {
    "read_file": EventKind.FILE_READ,
    "write_file": EventKind.FILE_WRITE,
    "create_file": EventKind.FILE_WRITE,
    "delete_file": EventKind.FILE_DELETE,
    "bash": EventKind.SHELL_CMD,
    "str_replace": EventKind.FILE_WRITE,
    "view": EventKind.FILE_READ,
}


class ClaudeCodeParser(BaseParser):
    """Parse ``.jsonl`` traces emitted by Claude Code.

    Each line is expected to be a JSON object with at least a ``type`` field.
    Unknown lines are silently skipped so the parser is forward-compatible.
    """

    format = TraceFormat.CLAUDE_CODE

    def can_parse(self, path: Path) -> bool:
        """Return ``True`` for ``.jsonl`` files."""
        return path.suffix.lower() == ".jsonl"

    def parse(self, path: Path) -> Trace:
        """Parse a Claude Code JSONL trace file.

        Args:
            path: Path to the ``.jsonl`` file.

        Returns:
            Populated :class:`~localitylens.core.trace.Trace`.

        Raises:
            ParseError: When the file cannot be read or is entirely malformed.
        """
        try:
            raw_lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise ParseError(f"Cannot read {path}: {exc}") from exc

        events: list[TraceEvent] = []
        for lineno, line in enumerate(raw_lines, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                log.warning("Skipping malformed JSON at line %d: %s", lineno, exc)
                continue
            event = self._convert(obj, sequence=len(events))
            if event is not None:
                events.append(event)

        if not events:
            raise ParseError(f"No parseable events found in {path}")

        trace = Trace(
            trace_id=self._make_trace_id(path),
            source=str(path),
            format=self.format,
            events=events,
            agent="claude-code",
        )
        log.debug("Parsed %d events from %s", len(events), path)
        return trace

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _convert(self, obj: dict, sequence: int) -> TraceEvent | None:
        """Convert a raw JSON object to a :class:`TraceEvent`.

        Returns ``None`` for record types we don't care about.
        """
        event_type = obj.get("type", "")
        ts = self._parse_ts(obj.get("timestamp"))

        if event_type == "tool_use":
            tool_name = obj.get("name", "")
            kind = _TOOL_KIND_MAP.get(tool_name, EventKind.TOOL_CALL)
            target = self._extract_target(obj.get("input", {}), tool_name)
            return TraceEvent(
                kind=kind,
                timestamp=ts,
                target=target,
                metadata={"tool": tool_name},
                sequence=sequence,
            )

        if event_type == "message":
            role = obj.get("role", "")
            if role == "assistant":
                return TraceEvent(
                    kind=EventKind.LLM_TURN,
                    timestamp=ts,
                    target="llm",
                    sequence=sequence,
                )

        return None

    @staticmethod
    def _parse_ts(raw: object) -> datetime:
        """Parse an ISO timestamp string, falling back to epoch."""
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime(1970, 1, 1, tzinfo=timezone.utc)

    @staticmethod
    def _extract_target(input_obj: dict, tool_name: str) -> str:
        """Best-effort extraction of the primary target from a tool input."""
        for key in ("path", "file_path", "command", "query"):
            if key in input_obj:
                return str(input_obj[key])
        return tool_name