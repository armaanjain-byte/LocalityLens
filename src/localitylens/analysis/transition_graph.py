from collections import Counter

from localitylens.utils.filters import is_real_file_target
from localitylens.core.metrics import (
    AnalysisReport,
    MetricResult,
    Severity,
    MetricNames,
    SeverityThresholds,
)
from localitylens.core.trace import Trace

class TransitionGraphAnalyzer:
    """
    Analyze file-to-file transition patterns.

    Measures:
    - transition concentration
    - dominant context flows
    - context instability
    """

    def analyze(self, trace: Trace, report: AnalysisReport) -> None:
        files = [
            e.target
            for e in trace.events
            if (
                e.kind.value in ("file_read", "file_write")
                and is_real_file_target(e.target)
            )
        ]

        transitions = []

        for i in range(len(files) - 1):
            src = files[i]
            dst = files[i + 1]

            if src != dst:
                transitions.append((src, dst))

        counts = Counter(transitions)

        total = sum(counts.values())

        dominant_ratio = (
            counts.most_common(1)[0][1] / total
            if total else 0.0
        )

        severity = self._classify(dominant_ratio)

        top_edges = ", ".join(
            f"{a}->{b}({count})"
            for (a, b), count in counts.most_common(5)
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
                        f"{a}->{b}": count
                        for (a, b), count in counts.items()
                    },
                },
            )
        )

    @staticmethod
    def _classify(ratio: float) -> Severity:

        t = SeverityThresholds.TRANSITION_CONCENTRATION

        if ratio <= t["low"]:
            return Severity.OK

        if ratio <= t["medium"]:
            return Severity.LOW

        if ratio <= t["high"]:
            return Severity.MEDIUM

        if ratio <= t["critical"]:
            return Severity.HIGH

        return Severity.CRITICAL