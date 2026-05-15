"""Parser for generic JSON array trace files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from localitylens.core.exceptions import ParseError
from localitylens.core.trace import EventKind, Trace, TraceEvent, TraceFormat
from localitylens.parsers.base import BaseParser
from localitylens.utils.logger import get_logger

log = get_logger(__name__)


class GenericJsonParser(BaseParser):
    """Parse a ``.json`` file containing an array of event objects.

    Expected schema per event::

        {
            "kind": "file_read",       # optional, mapped to EventKind
            "timestamp": "2024-...",   # ISO-8601, optional
            "target": "src/foo.py",    # optional
            ...                        # any extra keys stored in metadata
        }
    """

    format = TraceFormat.GENERIC_JSON

    def can_parse(self, path: Path) -> bool:
        """Return ``True`` for ``.json`` files."""
        return path.suffix.lower() == ".json"

    def parse(self, path: Path) -> Trace:
        """Parse a generic JSON trace file.

        Args:
            path: Path to the ``.json`` file.

        Returns:
            Populated :class:`~localitylens.core.trace.Trace`.

        Raises:
            ParseError: When the file cannot be read or parsed.
        """
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

        trace = Trace(
            trace_id=self._make_trace_id(path),
            source=str(path),
            format=self.format,
            events=events,
        )
        log.debug("Parsed %d events from %s", len(events), path)
        return trace

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _convert(self, obj: dict, sequence: int) -> TraceEvent:
        """Convert a raw dict to a :class:`TraceEvent`."""
        kind_raw = obj.pop("kind", "unknown")
        kind = EventKind(kind_raw) if kind_raw in EventKind._value2member_map_ else EventKind.UNKNOWN
        ts_raw = obj.pop("timestamp", None)
        ts = self._parse_ts(ts_raw)
        target = str(obj.pop("target", ""))
        return TraceEvent(
            kind=kind,
            timestamp=ts,
            target=target,
            metadata=dict(obj),
            sequence=sequence,
        )

    @staticmethod
    def _parse_ts(raw: object) -> datetime:
        """Parse an ISO timestamp string, falling back to epoch."""
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime(1970, 1, 1, tzinfo=timezone.utc)