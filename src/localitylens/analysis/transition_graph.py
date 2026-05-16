from collections import Counter

from localitylens.core.metrics import (
    AnalysisReport,
    MetricResult,
    Severity,
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
        and e.target not in (
            "session",
            "unknown_file",
            "search_operation",
        )
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
                name="transition_concentration",
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
        if ratio <= 0.05:
            return Severity.OK

        if ratio <= 0.10:
            return Severity.LOW

        if ratio <= 0.20:
            return Severity.MEDIUM

        if ratio <= 0.35:
            return Severity.HIGH

        return Severity.CRITICAL