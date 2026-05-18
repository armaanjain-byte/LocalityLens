"""Timestamp corruption integration coverage."""

from __future__ import annotations

import json

from localitylens.core.metrics import MetricNames
from localitylens.pipeline import run_pipeline


def test_invalid_timestamps_fall_back_without_pipeline_failure(tmp_path):
    trace_file = tmp_path / "bad_timestamps.json"
    trace_file.write_text(
        json.dumps(
            [
                {"kind": "file_read", "timestamp": "not-a-date", "target": "a.py"},
                {"kind": "file_read", "timestamp": None, "target": "b.py"},
            ]
        ),
        encoding="utf-8",
    )

    report = run_pipeline(trace_file)
    waste = report.by_name(MetricNames.WASTE_GAP_COUNT)[0]

    assert waste.value == 0.0


def test_out_of_order_timestamps_are_reported_in_pipeline(tmp_path):
    trace_file = tmp_path / "out_of_order.json"
    trace_file.write_text(
        json.dumps(
            [
                {"kind": "file_read", "timestamp": "2026-05-16T12:00:30Z", "target": "a.py"},
                {"kind": "file_read", "timestamp": "2026-05-16T12:00:00Z", "target": "b.py"},
            ]
        ),
        encoding="utf-8",
    )

    report = run_pipeline(trace_file)
    waste = report.by_name(MetricNames.WASTE_GAP_COUNT)[0]

    assert waste.extra["out_of_order_events"] == 1
