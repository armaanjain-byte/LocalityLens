"""Integration tests for the full analysis pipeline."""

from __future__ import annotations

import json

from localitylens.pipeline import run_pipeline
from localitylens.storage.db import ReportStore


def test_full_pipeline_on_generated_trace(tmp_path):
    trace_file = tmp_path / "trace.json"
    trace_file.write_text(
        json.dumps(
            [
                {"kind": "file_read", "timestamp": "2026-05-16T12:00:00Z", "target": "src/a.py"},
                {"kind": "file_read", "timestamp": "2026-05-16T12:00:01Z", "target": "src/b.py"},
                {"kind": "file_write", "timestamp": "2026-05-16T12:00:02Z", "target": "src/a.py"},
            ]
        ),
        encoding="utf-8",
    )

    report = run_pipeline(trace_file)
    store = ReportStore(tmp_path / "test.db")
    store.save(report)
    loaded = store.load(report.trace_id)

    assert loaded is not None
    assert {m.name for m in loaded.metrics} == {m.name for m in report.metrics}
    assert loaded.anomalies == report.anomalies
