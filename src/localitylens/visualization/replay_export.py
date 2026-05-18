"""Replay exporter: serializes trace transitions as temporal frames for the replay viewer."""

from __future__ import annotations

import json
from pathlib import Path

from localitylens.core.trace import Trace

# Cap the number of frames written to avoid multi-megabyte files that block the browser.
# Long traces should use a dedicated streaming viewer rather than a single JSON dump.
_MAX_FRAMES = 5_000


class ReplayExporter:
    """Export temporal transition frames for replay visualization."""

    def export(
        self,
        trace: Trace,
        output_path: str | Path = "replay_frames.json",
    ) -> str:
        """Serialize trace transitions to a JSON frame file.

        Args:
            trace:       Source trace.
            output_path: Destination file (default: replay_frames.json).

        Returns:
            The resolved output path string.
        """
        output = Path(output_path)
        frames: list[dict] = []
        previous: str | None = None

        for idx, event in enumerate(trace.events):
            if len(frames) >= _MAX_FRAMES:
                break

            target = getattr(event, "target", None)
            if not target:
                continue

            if previous is not None:
                raw_ts = getattr(event, "timestamp", idx)
                timestamp = raw_ts.isoformat() if hasattr(raw_ts, "isoformat") else raw_ts
                frames.append({
                    "step": idx,
                    "timestamp": timestamp,
                    "from": previous,
                    "to": target,
                    "event_type": event.kind.value,
                })

            previous = target

        output.write_text(json.dumps(frames, indent=2), encoding="utf-8")
        return str(output)