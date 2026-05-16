import math
from collections import Counter

from localitylens.core.metrics import (
    AnalysisReport,
    MetricResult,
    Severity,
)
from localitylens.core.trace import Trace


class ContextEntropyAnalyzer:
    """
    Measure semantic workflow fragmentation using
    transition entropy.

    Higher entropy:
        more chaotic context switching

    Lower entropy:
        more focused workflows
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
            a = files[i]
            b = files[i + 1]

            if a != b:
                transitions.append((a, b))

        counts = Counter(transitions)

        total = sum(counts.values())

        if total == 0:
            entropy = 0.0

        else:
            entropy = 0.0

            for count in counts.values():
                p = count / total
                entropy -= p * math.log2(p)

        severity = self._classify(entropy)

        report.metrics.append(
            MetricResult(
                name="context_entropy",
                value=round(entropy, 4),
                severity=severity,
                details=(
                    f"Transition entropy: {entropy:.4f}. "
                    "Higher values indicate fragmented workflows."
                ),
                extra={
                    "transition_count": total,
                },
            )
        )

    @staticmethod
    def _classify(entropy: float) -> Severity:
        if entropy <= 2:
            return Severity.OK

        if entropy <= 4:
            return Severity.LOW

        if entropy <= 6:
            return Severity.MEDIUM

        if entropy <= 8:
            return Severity.HIGH

        return Severity.CRITICAL