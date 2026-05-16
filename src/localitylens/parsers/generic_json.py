"""Parser for generic JSON array trace files with non-mutating transforms."""

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


class GenericJsonParser(BaseParser):
    """Parse a .json file containing an array of event objects."""

    format = TraceFormat.GENERIC_JSON

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() == ".json"

    def parse(self, path: Path) -> Trace:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ParseError(f"Cannot parse {path}: {exc}") from exc

        if not isinstance(data, list):
            raise ParseError(f"Expected a JSON array in {path}, got {type(data).__name__}")

        events: list[TraceEvent] = []
        for idx, raw in enumerate(data):
            if not isinstance(raw, dict):
                log.warning("Skipping non-object element at index %d", idx)
                continue
            events.append(self._convert(raw, sequence=idx))

        if not events:
            raise ParseError(f"No events found in {path}")

        return Trace(
            trace_id=self._make_trace_id(path),
            source=str(path),
            format=self.format,
            events=events,
        )

    # H-6 & M-6: Strict typing with non-destructive attribute projection filters
    def _convert(self, obj: dict[str, Any], sequence: int) -> TraceEvent:
        kind_raw = str(obj.get("kind", "unknown"))
        kind = EventKind(kind_raw) if kind_raw in EventKind._value2member_map_ else EventKind.UNKNOWN
        ts = self._parse_ts(obj.get("timestamp"))
        target = str(obj.get("target", ""))
        
        # Build metadata projection cleanly without stripping the source reference map
        metadata = {
            k: v for k, v in obj.items()
            if k not in ("kind", "timestamp", "target")
        }
        return TraceEvent(
            kind=kind,
            timestamp=ts,
            target=target,
            metadata=metadata,
            sequence=sequence,
        )

    @staticmethod
    def _parse_ts(raw: object) -> datetime:
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime(1970, 1, 1, tzinfo=timezone.utc)