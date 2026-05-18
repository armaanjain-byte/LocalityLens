"""Metric result models with optimized lookup logic."""

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


_SEVERITY_RANK: dict[Severity, int] = {s: i for i, s in enumerate(Severity)}


class MetricNames:
    BEHAVIORAL_ANOMALIES = "behavioral_anomalies"
    CHURN_RATIO = "churn_ratio"
    CONTEXT_ENTROPY = "context_entropy"
    DEPENDENCY_JUMP_RADIUS = "dependency_jump_radius"
    LOCALITY_SCORE = "locality_score"
    OSCILLATION_THRASHING = "oscillation_thrashing"
    SEMANTIC_CONTINUITY = "semantic_continuity"
    TRANSITION_CONCENTRATION = "transition_concentration"
    WASTE_GAP_COUNT = "waste_gap_count"


@dataclass
class MetricResult:
    """A single named metric computed over a trace."""

    name: str
    value: float
    severity: Severity = Severity.OK
    details: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisReport:
    """Aggregated output of all analysis engines for one trace."""

    trace_id: str
    metrics: list[MetricResult] = field(default_factory=list)
    summary: str = ""
    anomalies: list[dict[str, Any]] = field(default_factory=list)

    def sort_metrics(self) -> None:
        self.metrics.sort(key=lambda m: m.name)

    def worst_severity(self) -> Severity:
        """Return the highest Severity across all metrics in O(N) time."""
        if not self.metrics:
            return Severity.OK
        return max(self.metrics, key=lambda m: _SEVERITY_RANK[m.severity]).severity

    def by_name(self, name: str) -> list[MetricResult]:
        """Return all metrics whose name matches exactly."""
        return [m for m in self.metrics if m.name == name]
