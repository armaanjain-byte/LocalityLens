"""Transition graph analysis: measures file-to-file transition concentration."""

from __future__ import annotations

from collections import Counter

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.utils.filters import is_real_file_target


class TransitionGraphAnalyzer:
    """
    Analyse file-to-file transition patterns.

    dominant_ratio = count(most_common_transition) / total_transitions

    Interpretation (CORRECTED — was previously inverted):
    - High dominant_ratio (≥ 0.40): one transition dominates → focused workflow → OK/LOW
    - Low dominant_ratio (< 0.05):  completely uniform random jumping → CRITICAL

    A scattered agent that jumps unpredictably across many file pairs produces
    a near-zero dominant_ratio and should be flagged, not rewarded.
    """

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        files = [
            e.target
            for e in trace.events
            if e.kind.value in ("file_read", "file_write") and is_real_file_target(e.target)
        ]

        transitions = [
            (files[i], files[i + 1])
            for i in range(len(files) - 1)
            if files[i] != files[i + 1]
        ]

        counts: Counter[tuple[str, str]] = Counter(transitions)
        total = sum(counts.values())

        dominant_ratio = counts.most_common(1)[0][1] / total if total else 0.0
        severity = self._classify(dominant_ratio)

        top_edges = ", ".join(
            f"{a}->{b}({count})" for (a, b), count in counts.most_common(5)
        )

        report.metrics.append(
            MetricResult(
                name=MetricNames.TRANSITION_CONCENTRATION,
                value=round(dominant_ratio, 4),
                severity=severity,
                details=(
                    f"Dominant transition ratio: {dominant_ratio:.4f}. "
                    f"Top transitions: {top_edges or 'None'}"
                ),
                extra={
                    "total_transitions": total,
                    "top_edges": {
                        f"{a}->{b}": count for (a, b), count in counts.items()
                    },
                },
            )
        )

    @staticmethod
    def _classify(ratio: float) -> Severity:
        """
        Low ratio = fragmented / scattered = bad.
        High ratio = focused / repetitive = investigate but not automatically bad.

        Thresholds (dominant_ratio):
          >= 0.40 → OK      (one clear dominant path)
          >= 0.20 → LOW     (moderate focus)
          >= 0.10 → MEDIUM  (scattered)
          >= 0.05 → HIGH    (very scattered)
          <  0.05 → CRITICAL (uniform random walk across all pairs)
        """
        if ratio >= 0.40:
            return Severity.OK
        if ratio >= 0.20:
            return Severity.LOW
        if ratio >= 0.10:
            return Severity.MEDIUM
        if ratio >= 0.05:
            return Severity.HIGH
        return Severity.CRITICAL