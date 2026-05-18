"""Unit tests for report persistence."""

from __future__ import annotations

from pathlib import Path

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.storage.db import ReportStore


def test_report_round_trip_preserves_metrics_and_anomalies(tmp_path):
    report = AnalysisReport(trace_id="trace-1", summary="done")
    report.metrics.append(
        MetricResult(
            name=MetricNames.BEHAVIORAL_ANOMALIES,
            value=3.0,
            severity=Severity.HIGH,
            details="Found anomalies.",
            extra={"paths": {"b.py", "a.py"}, "nested": {"p": Path("src/a.py")}},
        )
    )
    report.anomalies.append(
        {"step": 7, "severity": "high", "type": "oscillation", "message": "a <-> b"}
    )

    store = ReportStore(tmp_path / "reports.db")
    store.save(report)

    loaded = store.load("trace-1")

    assert loaded is not None
    assert loaded.summary == "done"
    assert loaded.anomalies == report.anomalies
    assert loaded.metrics[0].extra["paths"] == ["a.py", "b.py"]
    assert loaded.metrics[0].extra["nested"]["p"] == str(Path("src/a.py"))


def test_existing_db_gets_anomalies_column(tmp_path):
    db_path = tmp_path / "old.db"
    store = ReportStore(db_path)
    with store._connection() as conn:
        conn.execute("ALTER TABLE reports RENAME TO reports_old")
        conn.execute(
            """
            CREATE TABLE reports (
                trace_id  TEXT PRIMARY KEY,
                summary   TEXT NOT NULL DEFAULT '',
                metrics   TEXT NOT NULL DEFAULT '[]',
                stored_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute("DROP TABLE reports_old")

    ReportStore(db_path)

    with store._read_connection() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(reports)").fetchall()}

    assert "anomalies" in columns
