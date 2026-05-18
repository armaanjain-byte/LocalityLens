"""Semantic continuity analysis: measures whether transitions stay inside dependency neighborhoods."""

from __future__ import annotations

from collections import deque

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

        graph = self._dependency_graph(smap)
        coherent = sum(
            1 for src, dst in transitions if self._within_dependency_neighborhood(graph, src, dst)
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
    def _dependency_graph(smap: SemanticMap) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = {path: set() for path in smap.files}
        for src, targets in smap.imports.items():
            graph.setdefault(src, set()).update(targets)
            for dst in targets:
                graph.setdefault(dst, set()).add(src)
        return graph

    @staticmethod
    def _within_dependency_neighborhood(
        graph: dict[str, set[str]],
        src: str,
        dst: str,
        max_hops: int = 2,
    ) -> bool:
        if src == dst:
            return True
        if src not in graph or dst not in graph:
            return False

        seen = {src}
        queue: deque[tuple[str, int]] = deque([(src, 0)])
        while queue:
            node, distance = queue.popleft()
            if distance >= max_hops:
                continue
            for neighbor in graph.get(node, set()):
                if neighbor == dst:
                    return True
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append((neighbor, distance + 1))
        return False
