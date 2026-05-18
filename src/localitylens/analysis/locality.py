"""Locality analysis: measures how focused the agent's file access is."""

from __future__ import annotations

from localitylens.config.settings import get_settings
from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace


class LocalityAnalyzer:
    """Compute a context-locality score for a trace.

    Locality measures how often the agent stays within the same file or a
    small neighbourhood of files in a sliding window.  A low score means the
    agent is constantly jumping across unrelated files.

    Requires SemanticMapper to have called register_touch() for each event
    so that smap.touch_sequence() returns a populated list.
    """

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        sequence = smap.touch_sequence()
        if len(sequence) < 2:
            report.metrics.append(
                MetricResult(
                    name=MetricNames.LOCALITY_SCORE,
                    value=1.0,
                    severity=Severity.OK,
                    details="Not enough events to compute locality.",
                )
            )
            return

        settings = get_settings()
        window = settings.thresholds.locality_window
        local_hits = 0
        total_windows = 0

        for i in range(len(sequence) - 1):
            context = set(sequence[max(0, i - window) : i + 1])
            semantic_context = set(context)
            for path in context:
                semantic_context.update(smap.semantic_neighbors(path))

            if sequence[i + 1] in semantic_context:
                local_hits += 1
            total_windows += 1

        score = local_hits / total_windows if total_windows else 1.0
        severity = self._classify(score)

        report.metrics.append(
            MetricResult(
                name=MetricNames.LOCALITY_SCORE,
                value=round(score, 4),
                severity=severity,
                details=(
                    f"{local_hits}/{total_windows} transitions stayed within a "
                    f"{window}-event semantic context window."
                ),
            )
        )

    @staticmethod
    def _classify(score: float) -> Severity:
        if score >= 0.75:
            return Severity.OK
        if score >= 0.55:
            return Severity.LOW
        if score >= 0.35:
            return Severity.MEDIUM
        if score >= 0.15:
            return Severity.HIGH
        return Severity.CRITICAL
