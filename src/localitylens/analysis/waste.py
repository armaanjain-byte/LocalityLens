"""Waste analysis: detects large idle gaps between events."""

from __future__ import annotations

from localitylens.config.settings import settings
from localitylens.core.metrics import (
    AnalysisReport,
    MetricNames,
    MetricResult,
    Severity,
)
from localitylens.core.trace import Trace


IDLE_GAP_THRESHOLD_SECONDS = settings.thresholds.waste_gap_seconds


class WasteAnalyzer:
    """Detect idle gaps that represent wasted context time.

    A gap larger than
    :attr:`~localitylens.config.settings.ThresholdSettings.waste_gap_seconds`
    between consecutive events is counted as a waste period.
    """

    def analyze(self, trace: Trace, report: AnalysisReport) -> None:
        """Append waste metrics to *report*.

        Args:
            trace: Source trace.
            report: Report to append metrics to (mutated in place).
        """

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

            delta = (
                curr.timestamp - prev.timestamp
            ).total_seconds()

            if delta >= IDLE_GAP_THRESHOLD_SECONDS:
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
                    f"≥{IDLE_GAP_THRESHOLD_SECONDS}s detected; "
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