"""Thrashing analysis: detect repeated context reload and retrieval loops."""

from __future__ import annotations

from collections import Counter, deque

from localitylens.core.metrics import AnalysisReport, MetricNames, MetricResult, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.utils.filters import is_real_file_target

OSCILLATION_PATTERN_LENGTH = 4
DEFAULT_CONTEXT_WINDOW = 5
REPEAT_WINDOW = 6


class ThrashingAnalyzer:
    """
    Detect context instability patterns in trace access order.

    This includes oscillating file loops of the form A -> B -> A -> B,
    re-accesses after a file leaves the active context window, repeated
    retrieval/search actions, and repeated reads in a small window.
    """

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        del smap

        files = [
            e.target
            for e in trace.events
            if e.kind.value in ("file_read", "file_write") and is_real_file_target(e.target)
        ]

        oscillations, possible_windows = self._detect_oscillations(files)
        reloads = self._detect_reloads_after_eviction(files)
        repeated_reads = self._detect_repeated_reads(files)
        repeated_searches = self._detect_repeated_searches(trace)

        oscillation_count = len(oscillations)
        total_signals = oscillation_count + reloads + repeated_reads + repeated_searches
        total_opportunities = max(1, possible_windows + len(files) + len(trace.events))
        rate = total_signals / total_opportunities

        pair_counts: Counter[tuple[str, str]] = Counter(oscillations)
        severity = self._classify(rate)

        top_pairs = ", ".join(
            f"{a}<->{b}({count})" for (a, b), count in pair_counts.most_common(5)
        )

        report.metrics.append(
            MetricResult(
                name=MetricNames.OSCILLATION_THRASHING,
                value=float(oscillation_count),
                severity=severity,
                details=(
                    f"{oscillation_count} oscillation loops, {reloads} reloads after eviction, "
                    f"{repeated_reads} repeated reads, and {repeated_searches} repeated searches "
                    f"detected (combined rate: {rate:.2%}). "
                    f"Top pairs: {top_pairs or 'None'}"
                ),
                extra={
                    "oscillations": oscillation_count,
                    "reloads_after_eviction": reloads,
                    "repeated_reads": repeated_reads,
                    "repeated_searches": repeated_searches,
                    "thrashing_signal_count": total_signals,
                    "thrashing_rate": round(rate, 4),
                    "oscillation_rate": round(
                        oscillation_count / possible_windows if possible_windows > 0 else 0.0,
                        4,
                    ),
                    "possible_windows": possible_windows,
                    "top_pairs": {
                        f"{a}<->{b}": count for (a, b), count in pair_counts.items()
                    },
                },
            )
        )

    @staticmethod
    def _detect_oscillations(files: list[str]) -> tuple[list[tuple[str, str]], int]:
        oscillations: list[tuple[str, str]] = []
        possible_windows = max(0, len(files) - (OSCILLATION_PATTERN_LENGTH - 1))

        for i in range(possible_windows):
            a, b, c, d = files[i : i + OSCILLATION_PATTERN_LENGTH]
            if a == c and b == d and a != b:
                oscillations.append((a, b))

        return oscillations, possible_windows

    @staticmethod
    def _detect_reloads_after_eviction(files: list[str]) -> int:
        active: deque[str] = deque(maxlen=DEFAULT_CONTEXT_WINDOW)
        active_set: set[str] = set()
        evicted: set[str] = set()
        reloads = 0

        for target in files:
            if target in evicted and target not in active_set:
                reloads += 1
                evicted.remove(target)

            if target in active_set:
                active.remove(target)
                active.append(target)
                continue

            if len(active) == active.maxlen:
                removed = active.popleft()
                active_set.remove(removed)
                evicted.add(removed)
            active.append(target)
            active_set.add(target)

        return reloads

    @staticmethod
    def _detect_repeated_reads(files: list[str]) -> int:
        repeats = 0
        window: deque[str] = deque(maxlen=REPEAT_WINDOW)

        for target in files:
            if target in window:
                repeats += 1
            window.append(target)

        return repeats

    @staticmethod
    def _detect_repeated_searches(trace: Trace) -> int:
        repeats = 0
        window: deque[str] = deque(maxlen=REPEAT_WINDOW)

        for event in trace.events:
            if not ThrashingAnalyzer._is_search_event(event):
                continue
            signature = ThrashingAnalyzer._search_signature(event)
            if signature in window:
                repeats += 1
            window.append(signature)

        return repeats

    @staticmethod
    def _is_search_event(event: object) -> bool:
        target = getattr(event, "target", "")
        metadata = getattr(event, "metadata", {}) or {}
        text = " ".join(
            str(value).lower()
            for value in (
                target,
                metadata.get("tool"),
                metadata.get("name"),
                metadata.get("command"),
                metadata.get("query"),
                metadata.get("pattern"),
            )
            if value
        )
        return any(token in text for token in ("search", "grep", "rg ", "find_file", "search_dir"))

    @staticmethod
    def _search_signature(event: object) -> str:
        metadata = getattr(event, "metadata", {}) or {}
        target = getattr(event, "target", "")
        return "|".join(
            str(value)
            for value in (
                target,
                metadata.get("query", ""),
                metadata.get("pattern", ""),
                metadata.get("path", ""),
                metadata.get("command", ""),
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
