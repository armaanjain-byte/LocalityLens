"""Large trace integration coverage."""

from __future__ import annotations

import json

from localitylens.core.metrics import MetricNames
from localitylens.pipeline import run_pipeline


def test_large_trace_completes_with_all_metrics(tmp_path):
    trace_file = tmp_path / "large.json"
    events = [
        {
            "kind": "file_read" if i % 5 else "file_write",
            "timestamp": f"2026-05-16T12:{i // 60:02d}:{i % 60:02d}Z",
            "target": f"src/file_{i % 25}.py",
        }
        for i in range(1200)
    ]
    trace_file.write_text(json.dumps(events), encoding="utf-8")

    report = run_pipeline(trace_file)

    metric_names = {metric.name for metric in report.metrics}
    assert MetricNames.LOCALITY_SCORE in metric_names
    assert MetricNames.SEMANTIC_CONTINUITY in metric_names
    assert len(report.metrics) >= 9
