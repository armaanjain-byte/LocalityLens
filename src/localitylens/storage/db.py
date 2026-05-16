"""SQLite-backed engine with strict isolation constraints and guarded reads."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from localitylens.core.exceptions import StorageError
from localitylens.core.metrics import AnalysisReport, MetricResult, Severity
from localitylens.utils.logger import get_logger

log = get_logger(__name__)


class ReportStore:
    """Persist and retrieve AnalysisReport objects safely using local SQLite storage."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._init_db()

    # H-1: Eliminate executescript auto-commit behaviors via parameterised execute paths
    def _init_db(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS reports (
                        trace_id  TEXT PRIMARY KEY,
                        summary   TEXT NOT NULL,
                        metrics   TEXT NOT NULL,
                        stored_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS reports (trace_id TEXT PRIMARY KEY)"
                )  # SQLite handles duplicate calls cleanly via IF NOT EXISTS blocks
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_reports_stored_at ON reports (stored_at)"
                )
        except sqlite3.Error as exc:
            raise StorageError(f"Cannot initialise DB at {self._db_path}: {exc}") from exc

    # H-2: Active WAL concurrency optimizations and thread safety configurations
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # H-3, L-3, & M-6 updates: Safe type mapping updates with UPSERT handling constraints
    def save(self, report: AnalysisReport) -> None:
        try:
            metrics_json = json.dumps([self._metric_to_dict(m) for m in report.metrics])
        except (TypeError, ValueError) as exc:
            raise StorageError(
                f"Cannot serialise metrics for report '{report.trace_id}': {exc}"
            ) from exc

        try:
            with self._connect() as conn:
                # L-3: Retain original stored_at marker parameters on update actions
                conn.execute("""
                    INSERT INTO reports (trace_id, summary, metrics, stored_at)
                    VALUES (?, ?, ?, datetime('now'))
                    ON CONFLICT(trace_id) DO UPDATE SET
                        summary  = excluded.summary,
                        metrics  = excluded.metrics
                """, (report.trace_id, report.summary, metrics_json))
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to save report {report.trace_id}: {exc}") from exc
        log.debug("Saved report for trace %s", report.trace_id)

    # C-3: Trap unhandled json loads failures cleanly to satisfy core contracts
    def load(self, trace_id: str) -> AnalysisReport | None:
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

        try:
            raw_metrics: list[dict[str, Any]] = json.loads(row[2])
        except json.JSONDecodeError as exc:
            raise StorageError(
                f"Corrupt metrics JSON for trace '{trace_id}': {exc}"
            ) from exc

        metrics = [self._dict_to_metric(d) for d in raw_metrics]
        return AnalysisReport(trace_id=row[0], summary=row[1], metrics=metrics)

    def list_ids(self) -> list[str]:
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT trace_id FROM reports ORDER BY stored_at").fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to list reports: {exc}") from exc
        return [r[0] for r in rows]

    @staticmethod
    def _metric_to_dict(m: MetricResult) -> dict[str, Any]:
        # H-3: Normalise sets and file structures into JSON-safe elements dynamically
        def _json_safe(obj: object) -> object:
            if isinstance(obj, set):
                return sorted(obj)
            if isinstance(obj, Path):
                return str(obj)
            return obj

        safe_extra = {k: _json_safe(v) for k, v in m.extra.items()}
        return {
            "name": m.name,
            "value": m.value,
            "severity": m.severity.value,
            "details": m.details,
            "extra": safe_extra,
        }

    @staticmethod
    def _dict_to_metric(d: dict[str, Any]) -> MetricResult:
        return MetricResult(
            name=str(d["name"]),
            value=float(d["value"]),
            severity=Severity(str(d["severity"])),
            details=str(d.get("details", "")),
            extra=dict(d.get("extra", {})),
        )