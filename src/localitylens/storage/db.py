"""SQLite-backed storage for persisting analysis reports."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from localitylens.core.exceptions import StorageError
from localitylens.core.metrics import AnalysisReport, MetricResult, Severity
from localitylens.utils.logger import get_logger

log = get_logger(__name__)


class ReportStore:
    """Persist and retrieve AnalysisReport objects using a local SQLite database."""

    # Write lock only — SQLite WAL mode supports concurrent readers, so we do
    # NOT serialize reads behind this lock (was incorrectly applied to reads before).
    _write_lock: threading.Lock = threading.Lock()

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._init_db()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager providing an isolated SQLite connection."""
        conn = sqlite3.connect(self._db_path, timeout=10.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        try:
            with self._write_lock:
                with self._connection() as conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS reports (
                            trace_id  TEXT PRIMARY KEY,
                            summary   TEXT NOT NULL DEFAULT '',
                            metrics   TEXT NOT NULL DEFAULT '[]',
                            stored_at TEXT NOT NULL DEFAULT (datetime('now'))
                        )
                    """)
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_reports_stored_at ON reports (stored_at)"
                    )
        except Exception as exc:
            raise StorageError(f"Cannot initialise DB at {self._db_path}: {exc}") from exc

    def save(self, report: AnalysisReport) -> None:
        try:
            metrics_json = json.dumps([self._metric_to_dict(m) for m in report.metrics])
        except (TypeError, ValueError) as exc:
            raise StorageError(
                f"Cannot serialise metrics for report '{report.trace_id}': {exc}"
            ) from exc

        try:
            with self._write_lock:
                with self._connection() as conn:
                    conn.execute("""
                        INSERT INTO reports (trace_id, summary, metrics, stored_at)
                        VALUES (?, ?, ?, datetime('now'))
                        ON CONFLICT(trace_id) DO UPDATE SET
                            summary  = excluded.summary,
                            metrics  = excluded.metrics
                    """, (report.trace_id, report.summary, metrics_json))
        except Exception as exc:
            raise StorageError(f"Failed to save report {report.trace_id}: {exc}") from exc

        log.debug("Saved report for trace %s", report.trace_id)

    def load(self, trace_id: str) -> AnalysisReport | None:
        """Load a report by trace ID. Does NOT acquire the write lock (readers are concurrent-safe)."""
        try:
            with self._connection() as conn:
                row = conn.execute(
                    "SELECT trace_id, summary, metrics FROM reports WHERE trace_id = ?",
                    (trace_id,),
                ).fetchone()
        except Exception as exc:
            raise StorageError(f"Failed to load report {trace_id}: {exc}") from exc

        if row is None:
            return None

        try:
            raw_metrics: list[dict[str, Any]] = json.loads(row[2])
        except json.JSONDecodeError as exc:
            raise StorageError(
                f"Corrupt metrics JSON for trace '{trace_id}': {exc}"
            ) from exc

        metrics = [self._dict_to_metric(d) for d in raw_metrics]
        return AnalysisReport(trace_id=row[0], summary=row[1], metrics=metrics)

    def list_ids(self) -> list[str]:
        """List all stored trace IDs ordered by insertion time. Does NOT acquire the write lock."""
        try:
            with self._connection() as conn:
                rows = conn.execute(
                    "SELECT trace_id FROM reports ORDER BY stored_at"
                ).fetchall()
        except Exception as exc:
            raise StorageError(f"Failed to list reports: {exc}") from exc
        return [r[0] for r in rows]

    @staticmethod
    def _metric_to_dict(m: MetricResult) -> dict[str, Any]:
        def _json_safe(obj: object) -> object:
            if isinstance(obj, set):
                return sorted(obj)
            if isinstance(obj, Path):
                return str(obj)
            return obj

        return {
            "name": m.name,
            "value": m.value,
            "severity": m.severity.value,
            "details": m.details,
            "extra": {k: _json_safe(v) for k, v in m.extra.items()},
        }

    @staticmethod
    def _dict_to_metric(d: dict[str, Any]) -> MetricResult:
        return MetricResult(
            name=str(d["name"]),
            value=float(d["value"]),
            severity=Severity(str(d["severity"])),
            details=d.get("details", ""),
            extra=dict(d.get("extra", {})),
        )