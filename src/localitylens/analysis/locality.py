"""Locality analysis: measures how focused the agent's file access is."""

from __future__ import annotations

from localitylens.config.settings import get_settings
from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.semantic.neighborhoods import SemanticNeighborhoods


class LocalityAnalyzer:
    """Compute a context-locality score for a trace.

    Locality measures how often the agent stays within the same file or a
    small neighbourhood of files in a sliding window.  A low score means the
    agent is constantly jumping across unrelated files.

    Requires SemanticMapper to have called register_touch() for each event
    so that smap.touch_sequence() returns a populated list.
    """

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        sequence = smap.concept_sequence()
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
        if not smap.definitions_by_symbol:
            self._analyze_file_locality(sequence, smap, report, window)
            return

        neighborhoods = SemanticNeighborhoods(smap)
        local_hits = 0
        overlap_total = 0.0
        total_windows = 0

        for i in range(len(sequence) - 1):
            context = set(sequence[max(0, i - window) : i + 1])
            semantic_context = set(context)
            next_symbol = sequence[i + 1]
            next_neighborhood = neighborhoods.neighborhood_for_symbol(next_symbol, radius=1)
            for symbol in context:
                semantic_context.update(neighborhoods.neighborhood_for_symbol(symbol, radius=2))

            if next_symbol in semantic_context:
                local_hits += 1
            overlap_total += neighborhoods.neighborhood_overlap(semantic_context, next_neighborhood)
            total_windows += 1

        retention = local_hits / total_windows if total_windows else 1.0
        overlap = overlap_total / total_windows if total_windows else 1.0
        dependency_continuity = neighborhoods.graph_locality(sequence, radius=2)
        score = (retention + overlap + dependency_continuity) / 3
        severity = self._classify(score)

        report.metrics.append(
            MetricResult(
                name=MetricNames.LOCALITY_SCORE,
                value=round(score, 4),
                severity=severity,
                details=(
                    f"{local_hits}/{total_windows} transitions stayed within a "
                    f"{window}-event semantic concept window."
                ),
                extra={
                    "semantic_retention": round(retention, 4),
                    "neighborhood_overlap": round(overlap, 4),
                    "dependency_continuity": round(dependency_continuity, 4),
                },
            )
        )

    @staticmethod
    def _analyze_file_locality(
        sequence: list[str],
        smap: SemanticMap,
        report: AnalysisReport,
        window: int,
    ) -> None:
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
        report.metrics.append(
            MetricResult(
                name=MetricNames.LOCALITY_SCORE,
                value=round(score, 4),
                severity=LocalityAnalyzer._classify(score),
                details=(
                    f"{local_hits}/{total_windows} transitions stayed within a "
                    f"{window}-event file context window."
                ),
                extra={"semantic_fallback": True},
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
