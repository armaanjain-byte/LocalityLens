"""Semantic continuity analysis: measures whether transitions stay inside dependency neighborhoods."""

from __future__ import annotations

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace


class SemanticContinuityAnalyzer:
    """
    Measure the fraction of consecutive transitions that stay inside
    semantically related dependency neighbourhoods.

    A transition src → dst is *coherent* when dst appears in src's import set
    OR src's reverse-import set (populated correctly by SemanticMapper.build()
    via add_import()).

    High score → focused, coherent workflow.
    Low score  → agent is jumping between unrelated files.
    """

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        transitions = smap.transitions

        if not transitions:
            report.metrics.append(
                MetricResult(
                    name=MetricNames.SEMANTIC_CONTINUITY,
                    value=1.0,
                    severity=Severity.OK,
                    details="No transitions available.",
                    extra={},
                )
            )
            return

        graph = smap.dependency_graph()
        distances_by_source: dict[str, dict[str, int]] = {}
        coherent = sum(
            1
            for src, dst in transitions
            if self._within_dependency_neighborhood(
                smap, graph, distances_by_source, src, dst
            )
        )

        score = coherent / len(transitions)
        severity = self._classify(score)

        report.metrics.append(
            MetricResult(
                name=MetricNames.SEMANTIC_CONTINUITY,
                value=round(score, 4),
                severity=severity,
                details=(
                    f"{coherent}/{len(transitions)} transitions "
                    "remained inside semantic dependency neighborhoods."
                ),
                extra={
                    "coherent_transitions": coherent,
                    "total_transitions": len(transitions),
                },
            )
        )

    @staticmethod
    def _classify(score: float) -> Severity:
        if score >= 0.80:
            return Severity.OK
        if score >= 0.60:
            return Severity.LOW
        if score >= 0.40:
            return Severity.MEDIUM
        if score >= 0.20:
            return Severity.HIGH
        return Severity.CRITICAL

    @staticmethod
    def _within_dependency_neighborhood(
        smap: SemanticMap,
        graph: dict[str, set[str]],
        distances_by_source: dict[str, dict[str, int]],
        src: str,
        dst: str,
        max_hops: int = 2,
    ) -> bool:
        if src == dst:
            return True
        if src not in graph or dst not in graph:
            return False

        if src not in distances_by_source:
            distances_by_source[src] = smap.shortest_distances(graph, src, max_hops=max_hops)
        distance = distances_by_source[src].get(dst)
        return distance is not None and distance <= max_hops
