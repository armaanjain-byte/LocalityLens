"""Dependency jump analysis: measures semantic distance between consecutive transitions."""

from __future__ import annotations

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace


class DependencyJumpAnalyzer:
    """
    Measure the fraction of transitions that cross unrelated dependency boundaries.

    A transition src → dst is considered *nearby* when dst appears in src's
    import set OR src's reverse-import set (i.e., they share a directory
    adjacency under the current heuristic).

    A high ratio means the agent is constantly jumping between unrelated files.

    Note: this metric is the complement of SemanticContinuityAnalyzer
    (dependency_jump_radius = 1 - semantic_continuity). Both are retained for
    explicit reporting clarity, but a future refactor should replace one with
    a genuinely distinct metric (e.g., average hop distance in the import graph).
    """

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
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

        distant = sum(
            1
            for src, dst in transitions
            if dst not in smap.imports.get(src, set())
            and dst not in smap.reverse_imports.get(src, set())
        )

        ratio = distant / len(transitions)
        severity = self._classify(ratio)

        report.metrics.append(
            MetricResult(
                name=MetricNames.DEPENDENCY_JUMP_RADIUS,
                value=round(ratio, 4),
                severity=severity,
                details=(
                    f"{distant}/{len(transitions)} transitions "
                    "crossed unrelated dependency boundaries."
                ),
                extra={
                    "distant_transitions": distant,
                    "total_transitions": len(transitions),
                },
            )
        )

    @staticmethod
    def _classify(ratio: float) -> Severity:
        if ratio <= 0.20:
            return Severity.OK
        if ratio <= 0.40:
            return Severity.LOW
        if ratio <= 0.60:
            return Severity.MEDIUM
        if ratio <= 0.80:
            return Severity.HIGH
        return Severity.CRITICAL