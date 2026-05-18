"""Thrashing analysis: detect oscillating A→B→A→B context-switch loops."""

from __future__ import annotations

from collections import Counter

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.utils.filters import is_real_file_target

OSCILLATION_PATTERN_LENGTH = 4


class ThrashingAnalyzer:
    """
    Detect oscillating context-switch loops of the form A → B → A → B.

    Reports both a raw oscillation count and a normalized oscillation rate
    (oscillations / possible_windows) so scores are comparable across traces
    of different lengths.
    """

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        files = [
            e.target
            for e in trace.events
            if e.kind.value in ("file_read", "file_write") and is_real_file_target(e.target)
        ]

        oscillations: list[tuple[str, str]] = []
        possible_windows = max(0, len(files) - (OSCILLATION_PATTERN_LENGTH - 1))

        for i in range(possible_windows):
            a, b, c, d = files[i : i + OSCILLATION_PATTERN_LENGTH]
            if a == c and b == d and a != b:
                oscillations.append((a, b))

        pair_counts: Counter[tuple[str, str]] = Counter(oscillations)
        total = len(oscillations)

        # Normalized rate: fraction of sliding windows that were oscillations
        rate = total / possible_windows if possible_windows > 0 else 0.0

        severity = self._classify(rate)

        top_pairs = ", ".join(
            f"{a}<->{b}({count})" for (a, b), count in pair_counts.most_common(5)
        )

        report.metrics.append(
            MetricResult(
                name=MetricNames.OSCILLATION_THRASHING,
                value=float(total),
                severity=severity,
                details=(
                    f"{total} oscillation loops detected "
                    f"(rate: {rate:.2%}). "
                    f"Top pairs: {top_pairs or 'None'}"
                ),
                extra={
                    "oscillations": total,
                    "oscillation_rate": round(rate, 4),
                    "possible_windows": possible_windows,
                    "top_pairs": {
                        f"{a}<->{b}": count for (a, b), count in pair_counts.items()
                    },
                },
            )
        )

    @staticmethod
    def _classify(rate: float) -> Severity:
        if rate <= 0.01:
            return Severity.OK
        if rate <= 0.05:
            return Severity.LOW
        if rate <= 0.15:
            return Severity.MEDIUM
        if rate <= 0.30:
            return Severity.HIGH
        return Severity.CRITICAL
