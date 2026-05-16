from collections import Counter

from localitylens.core.metrics import (
    AnalysisReport,
    MetricResult,
    Severity,
)
from localitylens.core.trace import Trace


class ThrashingAnalyzer:
    """
    Detect oscillating context-switch loops.

    Example:
        A → B → A → B

    This is much closer to real cognitive thrashing than
    simple repeated file access counts.
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

        oscillations = []

        for i in range(len(files) - 3):
            a, b, c, d = files[i:i + 4]

            if a == c and b == d and a != b:
                oscillations.append((a, b))

        pair_counts = Counter(oscillations)

        total = len(oscillations)

        severity = self._classify(total)

        top_pairs = ", ".join(
            f"{a}<->{b}({count})"
            for (a, b), count in pair_counts.most_common(5)
        )

        report.metrics.append(
            MetricResult(
                name="oscillation_thrashing",
                value=float(total),
                severity=severity,
                details=(
                    f"{total} oscillation loops detected. "
                    f"Top pairs: {top_pairs or 'None'}"
                ),
                extra={
                    "oscillations": total,
                    "top_pairs": {
                       f"{a}<->{b}": count
                       for (a, b), count in pair_counts.items()
                    },
                },
            )
        )

    @staticmethod
    def _classify(total: int) -> Severity:
        if total <= 5:
            return Severity.OK
        if total <= 20:
            return Severity.LOW
        if total <= 50:
            return Severity.MEDIUM
        if total <= 100:
            return Severity.HIGH

        return Severity.CRITICAL