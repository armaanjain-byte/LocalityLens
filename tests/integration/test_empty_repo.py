"""Repository indexing integration coverage for empty repositories."""

from __future__ import annotations

import json

from localitylens.core.metrics import MetricNames
from localitylens.pipeline import run_pipeline


def test_empty_repo_does_not_break_repository_aware_pipeline(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    trace_file = tmp_path / "trace.json"
    trace_file.write_text(
        json.dumps(
            [
                {"kind": "file_read", "timestamp": "2026-05-16T12:00:00Z", "target": "src/a.py"},
                {"kind": "file_read", "timestamp": "2026-05-16T12:00:01Z", "target": "src/b.py"},
            ]
        ),
        encoding="utf-8",
    )

    report = run_pipeline(trace_file, repo_path=repo)

    assert report.by_name(MetricNames.LOCALITY_SCORE)
