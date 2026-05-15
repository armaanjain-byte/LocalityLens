"""Thrashing analysis: detects repeated re-visiting of the same files."""

from __future__ import annotations

from collections import Counter

from localitylens.config.settings import settings
from localitylens.core.metrics import AnalysisReport, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap


class ThrashingAnalyzer:
    """Detect semantic thrashing in a trace.

    Thrashing occurs when the agent revisits the same files more than
    :attr:`~localitylens.config.settings.ThresholdSettings.thrash_repeat_limit`
    times without meaningful progress, suggesting it is stuck in a loop.
    """

    def analyze(self, smap: SemanticMap, report: AnalysisReport) -> None:
        """Append thrashing metrics to *report*.

        Args:
            smap: Semantic map built from the trace.
            report: Report to append metrics to (mutated in place).
        """
        counts: Counter[str] = Counter(smap.touch_sequence())
        limit = settings.thresholds.thrash_repeat_limit

        thrashing_files = {path: n for path, n in counts.items() if n >= limit}
        thrash_count = len(thrashing_files)
        total_files = len(counts)

        ratio = thrash_count / total_files if total_files else 0.0
        severity = self._classify(ratio, thrash_count)

        top = sorted(thrashing_files.items(), key=lambda x: -x[1])[:5]
        top_str = ", ".join(f"{p}({n})" for p, n in top)

        report.metrics.append(
            MetricResult(
                name="thrash_file_count",
                value=float(thrash_count),
                severity=severity,
                details=(
                    f"{thrash_count}/{total_files} files revisited ≥{limit}x. "
                    + (f"Top: {top_str}" if top_str else "None.")
                ),
                extra={"thrashing_files": thrashing_files},
            )
        )

    @staticmethod
    def _classify(ratio: float, count: int) -> Severity:
        if count == 0:
            return Severity.OK
        if ratio < 0.1:
            return Severity.LOW
        if ratio < 0.25:
            return Severity.MEDIUM
        if ratio < 0.5:
            return Severity.HIGH
        return Severity.CRITICAL