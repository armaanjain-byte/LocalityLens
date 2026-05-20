"""Human-readable findings generator for LocalityLens."""

from __future__ import annotations

from localitylens.core.metrics import (
    AnalysisReport,
    MetricNames,
)


class FindingsGenerator:
    """Convert raw metrics into readable workflow findings."""

    def generate(self, report: AnalysisReport) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []

        for metric in report.metrics:
            finding = self._metric_to_finding(metric.name, metric.value)

            if not finding:
                continue

            findings.append(
                {
                    "metric": metric.name,
                    "severity": metric.severity.value.upper(),
                    "title": finding["title"],
                    "description": finding["description"],
                    "details": metric.details,
                }
            )

        return findings

    def _metric_to_finding(
        self,
        metric_name: str,
        value: float,
    ) -> dict[str, str] | None:
        if metric_name == MetricNames.OSCILLATION_THRASHING:
            return {
                "title": "Heavy workflow thrashing detected",
                "description": (
                    "The agent repeatedly bounced between the same "
                    "semantic regions instead of progressing steadily."
                ),
            }

        if metric_name == MetricNames.CHURN_RATIO:
            return {
                "title": "High file churn observed",
                "description": (
                    "The workflow repeatedly rewrote or revisited files, "
                    "suggesting unstable context handling."
                ),
            }

        if metric_name == MetricNames.SEMANTIC_DRIFT:
            return {
                "title": "Semantic focus instability",
                "description": (
                    "The workflow frequently jumped between unrelated "
                    "areas of the codebase."
                ),
            }

        if metric_name == MetricNames.SEMANTIC_CONTINUITY:
            return {
                "title": "Low semantic continuity",
                "description": (
                    "The agent struggled to remain inside a stable "
                    "semantic neighborhood."
                ),
            }

        if metric_name == MetricNames.RETRIEVAL_PRESSURE:
            return {
                "title": "Excessive retrieval behavior",
                "description": (
                    "The workflow repeatedly reloaded previously "
                    "seen context."
                ),
            }

        if metric_name == MetricNames.COGNITIVE_LOAD:
            return {
                "title": "High cognitive load",
                "description": (
                    "Too many active semantic regions were involved "
                    "simultaneously."
                ),
            }

        if metric_name == MetricNames.CONTEXT_ENTROPY:
            return {
                "title": "Unstable workflow focus",
                "description": (
                    "The workflow changed direction frequently "
                    "instead of maintaining stable focus."
                ),
            }

        if metric_name == MetricNames.WASTE_GAP_COUNT:
            return {
                "title": "Large idle gaps detected",
                "description": (
                    "The session contained long inactive periods "
                    "between workflow events."
                ),
            }

        if metric_name == MetricNames.LOCALITY_SCORE:
            return {
                "title": "Weak context locality",
                "description": (
                    "The workflow failed to stay near recently "
                    "active semantic regions."
                ),
            }

        if metric_name == MetricNames.BEHAVIORAL_ANOMALIES:
            return {
                "title": "Behavioral instability detected",
                "description": (
                    "The workflow exhibited repeated anomalous "
                    "behavior patterns."
                ),
            }

        return None