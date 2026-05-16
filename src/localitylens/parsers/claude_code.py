"""Parser for Claude Code agent traces with null input validation checks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from localitylens.core.exceptions import ParseError
from localitylens.core.trace import EventKind, Trace, TraceEvent, TraceFormat
from localitylens.parsers.base import BaseParser
from localitylens.utils.logger import get_logger

log = get_logger(__name__)

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
    """Parse .jsonl traces emitted by Claude Code."""

    format = TraceFormat.CLAUDE_CODE

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() == ".jsonl"

    def parse(self, path: Path) -> Trace:
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
            if not isinstance(obj, dict):
                continue
            event = self._convert(obj, sequence=len(events))
            if event is not None:
                events.append(event)

        if not events:
            raise ParseError(f"No parseable events found in {path}")

        return Trace(
            trace_id=self._make_trace_id(path),
            source=str(path),
            format=self.format,
            events=events,
            agent="claude-code",
        )

    # M-6: Apply strict dictionary typing interfaces
    def _convert(self, obj: dict[str, Any], sequence: int) -> TraceEvent | None:
        event_type = obj.get("type", "")
        ts = self._parse_ts(obj.get("timestamp"))

        if event_type == "tool_use":
            tool_name = str(obj.get("name", ""))
            kind = _TOOL_KIND_MAP.get(tool_name, EventKind.TOOL_CALL)
            # C-1: Resolve null dictionary input failures gracefully
            raw_input = obj.get("input")
            input_obj: dict[str, Any] = raw_input if isinstance(raw_input, dict) else {}
            target = self._extract_target(input_obj, tool_name)
            return TraceEvent(
                kind=kind,
                timestamp=ts,
                target=target,
                metadata={"tool": tool_name},
                sequence=sequence,
            )

        if event_type == "message" and obj.get("role") == "assistant":
            return TraceEvent(
                kind=EventKind.LLM_TURN,
                timestamp=ts,
                target="llm",
                sequence=sequence,
            )

        return None

    @staticmethod
    def _parse_ts(raw: object) -> datetime:
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime(1970, 1, 1, tzinfo=timezone.utc)

    @staticmethod
    def _extract_target(input_obj: dict[str, Any], tool_name: str) -> str:
        for key in ("path", "file_path", "command", "query"):
            if key in input_obj:
                return str(input_obj[key])
        return tool_name