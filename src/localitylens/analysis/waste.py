"""Waste analysis: detects large idle gaps between events."""

from __future__ import annotations

from localitylens.config.settings import settings
from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace


class WasteAnalyzer:
    """Detect idle gaps that represent wasted context time.

    A gap larger than
    :attr:`~localitylens.config.settings.ThresholdSettings.waste_gap_seconds`
    between consecutive events is counted as a waste period.

    The threshold is read from ``settings`` on each call (not frozen at
    import time) so that config overrides and test fixtures take effect
    without requiring a module reload.
    """

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        # Read per-call so config overrides always take effect
        threshold = settings.thresholds.waste_gap_seconds

        events = trace.events

        if len(events) < 2:
            report.metrics.append(
                MetricResult(
                    name=MetricNames.WASTE_GAP_COUNT,
                    value=0.0,
                    severity=Severity.OK,
                    details="Not enough events to detect gaps.",
                )
            )
            return

        gaps: list[float] = []
        for prev, curr in zip(events, events[1:]):
            delta = (curr.timestamp - prev.timestamp).total_seconds()
            if delta >= threshold:
                gaps.append(delta)

        total_waste = sum(gaps)
        severity = self._classify(len(gaps))

        report.metrics.append(
            MetricResult(
                name=MetricNames.WASTE_GAP_COUNT,
                value=float(len(gaps)),
                severity=severity,
                details=(
                    f"{len(gaps)} idle gap(s) "
                    f"≥{threshold}s detected; "
                    f"total idle time: {total_waste:.1f}s."
                ),
                extra={
                    "total_waste_seconds": total_waste,
                    "gaps": gaps[:10],
                },
            )
        )

    @staticmethod
    def _classify(count: int) -> Severity:
        if count == 0:
            return Severity.OK
        if count <= 2:
            return Severity.LOW
        if count <= 5:
            return Severity.MEDIUM
        if count <= 10:
            return Severity.HIGH
        return Severity.CRITICAL