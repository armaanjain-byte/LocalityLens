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

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for read-only operations; it never commits."""
        conn = sqlite3.connect(self._db_path, timeout=10.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
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
                            anomalies TEXT NOT NULL DEFAULT '[]',
                            stored_at TEXT NOT NULL DEFAULT (datetime('now'))
                        )
                    """)
                    columns = {
                        row[1] for row in conn.execute("PRAGMA table_info(reports)").fetchall()
                    }
                    if "anomalies" not in columns:
                        conn.execute(
                            "ALTER TABLE reports ADD COLUMN anomalies TEXT NOT NULL DEFAULT '[]'"
                        )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_reports_stored_at ON reports (stored_at)"
                    )
        except Exception as exc:
            raise StorageError(f"Cannot initialise DB at {self._db_path}: {exc}") from exc

    def save(self, report: AnalysisReport) -> None:
        try:
            metrics_json = json.dumps([self._metric_to_dict(m) for m in report.metrics])
            anomalies_json = json.dumps(report.anomalies, cls=_SafeEncoder)
        except (TypeError, ValueError) as exc:
            raise StorageError(
                f"Cannot serialise report '{report.trace_id}': {exc}"
            ) from exc

        try:
            with self._write_lock:
                with self._connection() as conn:
                    conn.execute("""
                        INSERT INTO reports (trace_id, summary, metrics, anomalies, stored_at)
                        VALUES (?, ?, ?, ?, datetime('now'))
                        ON CONFLICT(trace_id) DO UPDATE SET
                            summary  = excluded.summary,
                            metrics  = excluded.metrics,
                            anomalies = excluded.anomalies,
                            stored_at = excluded.stored_at
                    """, (report.trace_id, report.summary, metrics_json, anomalies_json))
        except Exception as exc:
            raise StorageError(f"Failed to save report {report.trace_id}: {exc}") from exc

        log.debug("Saved report for trace %s", report.trace_id)

    def load(self, trace_id: str) -> AnalysisReport | None:
        """Load a report by trace ID. Does NOT acquire the write lock (readers are concurrent-safe)."""
        try:
            with self._read_connection() as conn:
                row = conn.execute(
                    "SELECT trace_id, summary, metrics, anomalies FROM reports WHERE trace_id = ?",
                    (trace_id,),
                ).fetchone()
        except Exception as exc:
            raise StorageError(f"Failed to load report {trace_id}: {exc}") from exc

        if row is None:
            return None

        try:
            raw_metrics: list[dict[str, Any]] = json.loads(row[2])
            anomalies: list[dict[str, Any]] = json.loads(row[3])
        except json.JSONDecodeError as exc:
            raise StorageError(
                f"Corrupt report JSON for trace '{trace_id}': {exc}"
            ) from exc

        metrics = [self._dict_to_metric(d) for d in raw_metrics]
        return AnalysisReport(trace_id=row[0], summary=row[1], metrics=metrics, anomalies=anomalies)

    def list_ids(self) -> list[str]:
        """List all stored trace IDs ordered by insertion time. Does NOT acquire the write lock."""
        try:
            with self._read_connection() as conn:
                rows = conn.execute(
                    "SELECT trace_id FROM reports ORDER BY stored_at"
                ).fetchall()
        except Exception as exc:
            raise StorageError(f"Failed to list reports: {exc}") from exc
        return [r[0] for r in rows]

    @staticmethod
    def _metric_to_dict(m: MetricResult) -> dict[str, Any]:
        return {
            "name": m.name,
            "value": m.value,
            "severity": m.severity.value,
            "details": m.details,
            "extra": json.loads(json.dumps(m.extra, cls=_SafeEncoder)),
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


class _SafeEncoder(json.JSONEncoder):
    """JSON encoder for report extras that may contain convenience containers."""

    def default(self, obj: object) -> object:
        if isinstance(obj, set):
            return sorted(obj)
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, Severity):
            return obj.value
        return super().default(obj)
