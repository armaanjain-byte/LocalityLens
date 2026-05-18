"""Churn analysis engine with drift-corrected boundary limits."""

from __future__ import annotations

from localitylens.config.settings import get_settings
from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import EventKind, Trace


class ChurnAnalyzer:
    """Measure write churn in a trace.

    churn_ratio = writes / (reads + writes)

    A high ratio indicates the agent is spending a disproportionate amount of
    its file I/O budget on writes rather than reads.
    """

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        reads = sum(1 for e in trace.events if e.kind is EventKind.FILE_READ)
        writes = sum(1 for e in trace.events if e.kind is EventKind.FILE_WRITE)
        total = reads + writes

        ratio = writes / total if total else 0.0
        severity = self._classify(ratio)

        report.metrics.append(
            MetricResult(
                name=MetricNames.CHURN_RATIO,
                value=round(ratio, 4),
                severity=severity,
                details=f"{writes} writes / {total} file events (reads + writes).",
                extra={"reads": reads, "writes": writes},
            )
        )

    @staticmethod
    def _classify(ratio: float) -> Severity:
        settings = get_settings()
        limit = settings.thresholds.churn_ratio_limit

        # Round to eliminate float-representation drift at boundaries
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
