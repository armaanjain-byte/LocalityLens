"""Cognitive load analysis."""

from __future__ import annotations

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace


class CognitiveLoadAnalyzer:
    """Estimate active semantic breadth in the analyzed workflow."""

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        del trace
        concepts = set(smap.concept_sequence())
        modules = {smap.module_for_symbol(symbol) for symbol in concepts}
        dependency_breadth = sum(len(smap.imports.get(path, set())) for path in smap.files)
        score = len(concepts) + len(modules) + dependency_breadth
        severity = self._classify(score)

        report.metrics.append(
            MetricResult(
                name=MetricNames.COGNITIVE_LOAD,
                value=float(score),
                severity=severity,
                details=(
                    f"{len(concepts)} active symbols across {len(modules)} modules "
                    f"with dependency breadth {dependency_breadth}."
                ),
                extra={
                    "active_symbols": len(concepts),
                    "active_modules": len(modules),
                    "dependency_breadth": dependency_breadth,
                },
            )
        )

    @staticmethod
    def _classify(score: int) -> Severity:
        if score <= 8:
            return Severity.OK
        if score <= 16:
            return Severity.LOW
        if score <= 32:
            return Severity.MEDIUM
        if score <= 64:
            return Severity.HIGH
        return Severity.CRITICAL
