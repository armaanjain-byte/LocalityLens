"""Narrative workflow summarizer."""

from __future__ import annotations

from localitylens.core.metrics import (
    AnalysisReport,
    MetricNames,
)


class SessionStoryGenerator:
    """Generate readable workflow narratives."""

    def generate(self, report: AnalysisReport) -> str:
        metric_map = {
            metric.name: metric
            for metric in report.metrics
        }

        story: list[str] = []

        story.append(
            "The workflow began by exploring multiple semantic "
            "regions and traversing several codebase areas."
        )

        thrashing = metric_map.get(
            MetricNames.OSCILLATION_THRASHING
        )

        churn = metric_map.get(
            MetricNames.CHURN_RATIO
        )

        drift = metric_map.get(
            MetricNames.SEMANTIC_DRIFT
        )

        entropy = metric_map.get(
            MetricNames.CONTEXT_ENTROPY
        )

        if thrashing and thrashing.value > 50:
            story.append(
                "Repeated oscillation behavior emerged as the "
                "agent revisited previously abandoned context "
                "instead of maintaining forward progress."
            )

        if churn and churn.value > 0.4:
            story.append(
                "The workflow exhibited unstable file churn, "
                "with many repeated revisits and modifications."
            )

        if drift and drift.value > 0.5:
            story.append(
                "Semantic focus deteriorated as the workflow "
                "jumped across unrelated code regions."
            )

        if entropy and entropy.value > 0.7:
            story.append(
                "Workflow stability eventually collapsed into "
                "high-entropy context switching behavior."
            )

        story.append(
            "Overall, the session demonstrated significant "
            "context instability and reduced semantic locality."
        )

        return " ".join(story)