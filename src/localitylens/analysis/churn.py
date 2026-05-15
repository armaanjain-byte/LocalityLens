"""Churn analysis: ratio of writes to total file events."""

from __future__ import annotations

from localitylens.config.settings import settings
from localitylens.core.metrics import AnalysisReport, MetricResult, Severity
from localitylens.core.trace import EventKind, Trace


class ChurnAnalyzer:
    """Measure write churn in a trace.

    A high write-to-read ratio suggests the agent is rewriting code it just
    read, which indicates poor context retention or thrashing.
    """

    def analyze(self, trace: Trace, report: AnalysisReport) -> None:
        """Append churn metrics to *report*.

        Args:
            trace: Source trace.
            report: Report to append metrics to (mutated in place).
        """
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
        if ratio <= limit * 0.5:
            return Severity.OK
        if ratio <= limit:
            return Severity.LOW
        if ratio <= limit * 1.5:
            return Severity.MEDIUM
        if ratio <= limit * 2.0:
            return Severity.HIGH
        return Severity.CRITICAL