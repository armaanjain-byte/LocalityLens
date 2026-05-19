"""Context entropy analysis: measures semantic workflow fragmentation."""

from __future__ import annotations

import math
from collections import Counter
from typing import Hashable

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.semantic.neighborhoods import SemanticNeighborhoods
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
        sequence = smap.concept_sequence()
        if not sequence:
            sequence = [
                e.target
                for e in trace.events
                if e.kind.value in ("file_read", "file_write") and is_real_file_target(e.target)
            ]
        transition_items: list[tuple[Hashable, Hashable]]
        if not smap.definitions_by_symbol:
            transition_items = [
                (sequence[i], sequence[i + 1])
                for i in range(len(sequence) - 1)
                if sequence[i] != sequence[i + 1]
            ]
        else:
            neighborhoods = SemanticNeighborhoods(smap).neighborhoods_for_sequence(sequence, radius=1)
            transition_items = [
                (frozenset(neighborhoods[i]), frozenset(neighborhoods[i + 1]))
                for i in range(len(neighborhoods) - 1)
                if neighborhoods[i] != neighborhoods[i + 1]
            ]

        counts = Counter(transition_items)
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
                    f"({n_unique} unique semantic neighborhood transitions, {total} total). "
                    "Higher values indicate volatile semantic focus."
                ),
                extra={
                    "semantic_transition_count": total,
                    "unique_neighborhood_pairs": n_unique,
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
