"""Metric result models with optimised lookup logic."""

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


# M-1: Pre-computed rank mapping for O(1) weight comparisons
_SEVERITY_RANK: dict[Severity, int] = {s: i for i, s in enumerate(Severity)}

class MetricNames:
    BEHAVIORAL_ANOMALIES = "behavioral_anomalies"
    CHURN_RATIO = "churn_ratio"
    CONTEXT_ENTROPY = "context_entropy"
    DEPENDENCY_JUMP_RADIUS = "dependency_jump_radius"
    OSCILLATION_THRASHING = "oscillation_thrashing"
    SEMANTIC_CONTINUITY = "semantic_continuity"
    TRANSITION_CONCENTRATION = "transition_concentration"
    WASTE_GAP_COUNT = "waste_gap_count"

class SeverityThresholds:

    TRANSITION_CONCENTRATION = {
        "low": 0.05,
        "medium": 0.10,
        "high": 0.20,
        "critical": 0.35,
    }

    SEMANTIC_CONTINUITY = {
        "critical": 0.20,
        "high": 0.40,
        "medium": 0.60,
        "low": 0.80,
    }

    DEPENDENCY_JUMP_RADIUS = {
        "low": 0.20,
        "medium": 0.40,
        "high": 0.60,
        "critical": 0.80,
    }

    CHURN_RATIO = {
        "low": 0.20,
        "medium": 0.40,
        "high": 0.60,
        "critical": 0.80,
    }




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
    
    def sort_metrics(self) -> None:
        self.metrics.sort(key=lambda m: m.name)

    def worst_severity(self) -> Severity:
        """Return the highest Severity across all metrics in linear O(N) time."""
        if not self.metrics:
            return Severity.OK
        return max(self.metrics, key=lambda m: _SEVERITY_RANK[m.severity]).severity

    def by_name(self, name: str) -> list[MetricResult]:
        """Return all metrics whose name matches exactly."""
        return [m for m in self.metrics if m.name == name]