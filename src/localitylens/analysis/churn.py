"""Churn analysis engine with drift-corrected boundary limits."""

from __future__ import annotations

from localitylens.config.settings import settings
from localitylens.core.metrics import AnalysisReport, MetricResult, Severity
from localitylens.core.trace import EventKind, Trace


class ChurnAnalyzer:
    """Measure write churn in a trace."""

    def analyze(self, trace: Trace, report: AnalysisReport) -> None:
        reads = sum(1 for e in trace.events if e.kind is EventKind.FILE_READ)
        writes = sum(1 for e in trace.events if e.kind is EventKind.FILE_WRITE)
        total = reads + writes

        ratio = writes / total if total else 0.0
        severity = self._classify(ratio)

        report.metrics.append(
            MetricResult(
                name="churn_ratio",
                value=round(ratio, 4),
                severity=severity,
                details=f"{writes} writes / {total} file events (reads + writes).",
                extra={"reads": reads, "writes": writes},
            )
        )

    @staticmethod
    def _classify(ratio: float) -> Severity:
        limit = settings.thresholds.churn_ratio_limit
        
        # M-5: Round threshold limits explicitly to eliminate float representation drifts
        t_ok = round(limit * 0.5, 10)
        t_low = round(limit, 10)
        t_medium = round(limit * 1.5, 10)
        t_high = round(limit * 2.0, 10)

        if ratio <= t_ok:
            return Severity.OK
        if ratio <= t_low:
            return Severity.LOW
        if ratio <= t_medium:
            return Severity.MEDIUM
        if ratio <= t_high:
            return Severity.HIGH
        return Severity.CRITICAL