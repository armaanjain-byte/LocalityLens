"""Dependency jump analysis: measures graph distance between consecutive transitions."""

from __future__ import annotations

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace


class DependencyJumpAnalyzer:
    """
    Measure average dependency-graph hop distance for consecutive file transitions.

    Direct imports or reverse imports have radius 1. Disconnected transitions
    receive a conservative penalty based on graph size and are reported
    separately so the numeric score is not mistaken for a probability.
    """

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        del trace

        transitions = smap.transitions

        if not transitions:
            report.metrics.append(
                MetricResult(
                    name=MetricNames.DEPENDENCY_JUMP_RADIUS,
                    value=0.0,
                    severity=Severity.OK,
                    details="No transitions available.",
                    extra={},
                )
            )
            return

        graph = smap.dependency_graph()
        disconnected_penalty = max(2, len(graph))
        distances: list[int] = []
        distances_by_source: dict[str, dict[str, int]] = {}
        disconnected = 0

        for src, dst in transitions:
            if src not in distances_by_source:
                distances_by_source[src] = smap.shortest_distances(graph, src)
            distance = distances_by_source[src].get(dst)
            if distance is None:
                disconnected += 1
                distance = disconnected_penalty
            distances.append(distance)

        average_radius = sum(distances) / len(distances)
        disconnected_ratio = disconnected / len(transitions)
        severity = self._classify(average_radius, disconnected_ratio)

        report.metrics.append(
            MetricResult(
                name=MetricNames.DEPENDENCY_JUMP_RADIUS,
                value=round(average_radius, 4),
                severity=severity,
                details=(
                    f"Average dependency jump radius: {average_radius:.4f} hops "
                    f"({disconnected}/{len(transitions)} disconnected transitions)."
                ),
                extra={
                    "average_radius": round(average_radius, 4),
                    "disconnected_transitions": disconnected,
                    "total_transitions": len(transitions),
                },
            )
        )

    @staticmethod
    def _classify(average_radius: float, disconnected_ratio: float) -> Severity:
        if disconnected_ratio >= 0.80:
            return Severity.CRITICAL
        if disconnected_ratio >= 0.50:
            return Severity.HIGH
        if average_radius <= 1.0:
            return Severity.OK
        if average_radius <= 2.0:
            return Severity.LOW
        if average_radius <= 3.0:
            return Severity.MEDIUM
        if average_radius <= 5.0:
            return Severity.HIGH
        return Severity.CRITICAL
