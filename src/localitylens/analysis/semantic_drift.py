"""Semantic drift analysis."""

from __future__ import annotations

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.semantic.neighborhoods import SemanticNeighborhoods


class SemanticDriftAnalyzer:
    """Measure how rapidly semantic focus moves between regions."""

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        del trace
        sequence = smap.concept_sequence()
        if len(sequence) < 2:
            report.metrics.append(
                MetricResult(
                    name=MetricNames.SEMANTIC_DRIFT,
                    value=0.0,
                    severity=Severity.OK,
                    details="Not enough semantic concepts to measure drift.",
                    extra={},
                )
            )
            return

        neighborhoods = SemanticNeighborhoods(smap)
        distances = [
            neighborhoods.symbol_distance(source, target, max_hops=4)
            for source, target in zip(sequence, sequence[1:])
        ]
        disconnected = sum(1 for distance in distances if distance is None)
        drift = disconnected / len(distances)
        severity = self._classify(drift)

        report.metrics.append(
            MetricResult(
                name=MetricNames.SEMANTIC_DRIFT,
                value=round(drift, 4),
                severity=severity,
                details=f"{disconnected}/{len(distances)} semantic transitions were disconnected.",
                extra={"disconnected_transitions": disconnected, "total_transitions": len(distances)},
            )
        )

    @staticmethod
    def _classify(drift: float) -> Severity:
        if drift <= 0.10:
            return Severity.OK
        if drift <= 0.25:
            return Severity.LOW
        if drift <= 0.50:
            return Severity.MEDIUM
        if drift <= 0.75:
            return Severity.HIGH
        return Severity.CRITICAL
