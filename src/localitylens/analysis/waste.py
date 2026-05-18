"""Waste analysis: detects large idle gaps between events."""

from __future__ import annotations

from localitylens.config.settings import get_settings
from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.utils.logger import get_logger

log = get_logger(__name__)


class WasteAnalyzer:
    """Detect idle gaps that represent wasted context time."""

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        del smap

        settings = get_settings()
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
        out_of_order = 0
        for prev, curr in zip(events, events[1:]):
            delta = (curr.timestamp - prev.timestamp).total_seconds()
            if delta < 0:
                out_of_order += 1
                log.warning(
                    "Out-of-order events at seq %d -> %d (delta=%.1fs)",
                    prev.sequence,
                    curr.sequence,
                    delta,
                )
                continue
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
                    f">={threshold}s detected; "
                    f"total idle time: {total_waste:.1f}s."
                ),
                extra={
                    "total_waste_seconds": total_waste,
                    "gaps": gaps[:10],
                    "out_of_order_events": out_of_order,
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
