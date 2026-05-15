"""Metric result models produced by the analysis engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Classification of how serious a detected issue is."""

    OK = "ok"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MetricResult:
    """A single named metric computed over a trace.

    Attributes:
        name: Machine-readable metric identifier.
        value: Numeric measurement.
        severity: Qualitative classification of the value.
        details: Human-readable explanation.
        extra: Engine-specific supplementary data.
    """

    name: str
    value: float
    severity: Severity = Severity.OK
    details: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisReport:
    """Aggregated output of all analysis engines for one trace.

    Attributes:
        trace_id: Identifier of the analysed trace.
        metrics: All computed :class:`MetricResult` objects.
        summary: One-line human-readable verdict.
    """

    trace_id: str
    metrics: list[MetricResult] = field(default_factory=list)
    summary: str = ""

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def worst_severity(self) -> Severity:
        """Return the highest :class:`Severity` across all metrics."""
        order = list(Severity)
        worst = Severity.OK
        for m in self.metrics:
            if order.index(m.severity) > order.index(worst):
                worst = m.severity
        return worst

    def by_name(self, name: str) -> list[MetricResult]:
        """Return all metrics whose *name* matches exactly."""
        return [m for m in self.metrics if m.name == name]