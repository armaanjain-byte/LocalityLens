from localitylens.core.metrics import (
    AnalysisReport,
    MetricResult,
    Severity,
    MetricNames,
)
from localitylens.core.semantic_map import SemanticMap


class DependencyJumpAnalyzer:
    """
    Measure semantic jump distance between
    consecutive file transitions.

    Nearby dependency transitions:
        low radius (good)

    Unrelated jumps:
        high radius (bad)
    """

    def analyze(self, smap: SemanticMap, report: AnalysisReport) -> None:
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

        distant = 0

        for src, dst in transitions:
            imports = smap.imports.get(src, set())
            reverse = smap.reverse_imports.get(src, set())

            if dst not in imports and dst not in reverse:
                distant += 1

        ratio = distant / len(transitions)

        severity = self._classify(ratio)

        report.metrics.append(
            MetricResult(
                name="dependency_jump_radius",
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