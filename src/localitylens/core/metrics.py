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

    def worst_severity(self) -> Severity:
        """Return the highest Severity across all metrics in linear O(N) time."""
        if not self.metrics:
            return Severity.OK
        return max(self.metrics, key=lambda m: _SEVERITY_RANK[m.severity]).severity

    def by_name(self, name: str) -> list[MetricResult]:
        """Return all metrics whose name matches exactly."""
        return [m for m in self.metrics if m.name == name]