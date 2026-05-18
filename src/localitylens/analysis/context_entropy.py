"""Context entropy analysis: measures semantic workflow fragmentation."""

from __future__ import annotations

import math
from collections import Counter

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.utils.filters import is_real_file_target


class ContextEntropyAnalyzer:
    """
    Measure semantic workflow fragmentation using transition entropy.

    Uses *relative* entropy (H / log2(N)) which normalises the raw Shannon
    entropy to [0, 1] regardless of how many unique transition pairs exist.
    This makes the score comparable across traces of different sizes.

        0.0 → perfectly focused (one dominant transition)
        1.0 → maximally uniform random jumping across all pairs
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

        counts = Counter(transitions)
        total = sum(counts.values())
        n_unique = len(counts)

        if total == 0 or n_unique <= 1:
            # Single transition pair → zero entropy → perfectly focused
            relative_entropy = 0.0
        else:
            raw_entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
            max_entropy = math.log2(n_unique)   # theoretical maximum for n_unique pairs
            relative_entropy = raw_entropy / max_entropy if max_entropy > 0 else 0.0

        severity = self._classify(relative_entropy)

        report.metrics.append(
            MetricResult(
                name=MetricNames.CONTEXT_ENTROPY,
                value=round(relative_entropy, 4),
                severity=severity,
                details=(
                    f"Relative transition entropy: {relative_entropy:.4f} "
                    f"({n_unique} unique transition pairs, {total} total). "
                    "Higher values indicate fragmented workflows."
                ),
                extra={
                    "transition_count": total,
                    "unique_pairs": n_unique,
                },
            )
        )

    @staticmethod
    def _classify(relative_entropy: float) -> Severity:
        """Classify relative entropy in [0, 1]."""
        if relative_entropy <= 0.25:
            return Severity.OK
        if relative_entropy <= 0.50:
            return Severity.LOW
        if relative_entropy <= 0.70:
            return Severity.MEDIUM
        if relative_entropy <= 0.85:
            return Severity.HIGH
        return Severity.CRITICAL