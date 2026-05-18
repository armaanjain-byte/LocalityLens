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


# Pre-computed rank mapping for O(1) weight comparisons
_SEVERITY_RANK: dict[Severity, int] = {s: i for i, s in enumerate(Severity)}


class MetricNames:
    BEHAVIORAL_ANOMALIES = "behavioral_anomalies"
    CHURN_RATIO = "churn_ratio"
    CONTEXT_ENTROPY = "context_entropy"
    DEPENDENCY_JUMP_RADIUS = "dependency_jump_radius"
    LOCALITY_SCORE = "locality_score"                   # was missing — LocalityAnalyzer uses this
    OSCILLATION_THRASHING = "oscillation_thrashing"
    SEMANTIC_CONTINUITY = "semantic_continuity"
    TRANSITION_CONCENTRATION = "transition_concentration"
    WASTE_GAP_COUNT = "waste_gap_count"


class SeverityThresholds:
    # TransitionConcentration: low dominant_ratio = fragmented = bad.
    # Thresholds are LOWER bounds below which we escalate severity.
    # (ratio >= 0.40 means one path dominates heavily → focused, OK/LOW)
    # (ratio <  0.05 means perfectly uniform random walk → CRITICAL)
    TRANSITION_CONCENTRATION = {
        "ok_min": 0.40,      # ratio >= 0.40 → OK (one clear dominant path)
        "low_min": 0.20,     # ratio >= 0.20 → LOW
        "medium_min": 0.10,  # ratio >= 0.10 → MEDIUM
        "high_min": 0.05,    # ratio >= 0.05 → HIGH
        # below 0.05          → CRITICAL (completely uniform random jumping)
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
    anomalies: list[dict] = field(default_factory=list)   # was set as dynamic attr by AnomalyAnalyzer

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