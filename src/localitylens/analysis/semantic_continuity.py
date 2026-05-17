from localitylens.core.metrics import (
    AnalysisReport,
    MetricResult,
    Severity,
    MetricNames,
)
from localitylens.core.semantic_map import SemanticMap


class SemanticContinuityAnalyzer:
    """
    Measures whether consecutive transitions stay
    inside semantically related dependency neighborhoods.
    """

    def analyze(self, smap: SemanticMap, report: AnalysisReport) -> None:
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

        coherent = 0

        for src, dst in transitions:
            imports = smap.imports.get(src, set())
            reverse = smap.reverse_imports.get(src, set())

            if dst in imports or dst in reverse:
                coherent += 1

        score = coherent / len(transitions)

        severity = self._classify(score)

        report.metrics.append(
            MetricResult(
                name="semantic_continuity",
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