"""Retrieval pressure analysis."""

from __future__ import annotations

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.semantic.context_window import ContextWindowSimulator


class RetrievalPressureAnalyzer:
    """Measure how often semantic context must be reloaded."""

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        del trace
        concepts = smap.concept_sequence()
        state = ContextWindowSimulator(capacity=8).simulate(
            concepts,
            symbol_to_module={symbol: smap.module_for_symbol(symbol) for symbol in concepts},
        )
        pressure = state.reload_pressure
        severity = self._classify(pressure)

        report.metrics.append(
            MetricResult(
                name=MetricNames.RETRIEVAL_PRESSURE,
                value=round(pressure, 4),
                severity=severity,
                details=f"{state.reload_count} semantic reloads after eviction.",
                extra={
                    "reload_count": state.reload_count,
                    "eviction_count": state.eviction_count,
                    "compression_ratio": state.compression_ratio,
                },
            )
        )

    @staticmethod
    def _classify(pressure: float) -> Severity:
        if pressure <= 0.02:
            return Severity.OK
        if pressure <= 0.08:
            return Severity.LOW
        if pressure <= 0.16:
            return Severity.MEDIUM
        if pressure <= 0.30:
            return Severity.HIGH
        return Severity.CRITICAL
