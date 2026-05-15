"""SQLite-backed storage for persisting analysis reports."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from localitylens.core.exceptions import StorageError
from localitylens.core.metrics import AnalysisReport, MetricResult, Severity
from localitylens.utils.logger import get_logger

log = get_logger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS reports (
    trace_id  TEXT PRIMARY KEY,
    summary   TEXT NOT NULL,
    metrics   TEXT NOT NULL,    -- JSON array
    stored_at TEXT DEFAULT (datetime('now'))
);
"""


class ReportStore:
    """Persist and retrieve :class:`~localitylens.core.metrics.AnalysisReport`
    objects using a local SQLite database.

    Args:
        db_path: Filesystem path for the SQLite file.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, report: AnalysisReport) -> None:
        """Persist *report*, replacing any existing entry with the same ID.

        Args:
            report: Report to store.

        Raises:
            StorageError: On database write failure.
        """
        metrics_json = json.dumps([self._metric_to_dict(m) for m in report.metrics])
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO reports (trace_id, summary, metrics) VALUES (?, ?, ?)",
                    (report.trace_id, report.summary, metrics_json),
                )
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to save report {report.trace_id}: {exc}") from exc
        log.debug("Saved report for trace %s", report.trace_id)

    def load(self, trace_id: str) -> AnalysisReport | None:
        """Load a previously saved report by *trace_id*.

        Args:
            trace_id: Identifier of the trace.

        Returns:
            :class:`AnalysisReport` if found, ``None`` otherwise.

        Raises:
            StorageError: On database read failure.
        """
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT trace_id, summary, metrics FROM reports WHERE trace_id = ?",
                    (trace_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to load report {trace_id}: {exc}") from exc

        if row is None:
            return None

        raw_metrics = json.loads(row[2])
        metrics = [self._dict_to_metric(d) for d in raw_metrics]
        return AnalysisReport(trace_id=row[0], summary=row[1], metrics=metrics)

    def list_ids(self) -> list[str]:
        """Return all stored trace IDs.

        Returns:
            List of trace ID strings.

        Raises:
            StorageError: On database read failure.
        """
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT trace_id FROM reports ORDER BY stored_at").fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to list reports: {exc}") from exc
        return [r[0] for r in rows]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        try:
            with self._connect() as conn:
                conn.executescript(_CREATE_SQL)
        except sqlite3.Error as exc:
            raise StorageError(f"Cannot initialise DB at {self._db_path}: {exc}") from exc

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    @staticmethod
    def _metric_to_dict(m: MetricResult) -> dict:
        return {
            "name": m.name,
            "value": m.value,
            "severity": m.severity.value,
            "details": m.details,
            "extra": m.extra,
        }

    @staticmethod
    def _dict_to_metric(d: dict) -> MetricResult:
        return MetricResult(
            name=d["name"],
            value=d["value"],
            severity=Severity(d["severity"]),
            details=d.get("details", ""),
            extra=d.get("extra", {}),
        )