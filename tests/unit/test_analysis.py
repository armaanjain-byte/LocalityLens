"""Unit tests for LocalityLens stateless analysis engines."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from localitylens.analysis.anomaly import AnomalyAnalyzer
from localitylens.analysis.churn import ChurnAnalyzer
from localitylens.analysis.context_entropy import ContextEntropyAnalyzer
from localitylens.analysis.dependency_jump import DependencyJumpAnalyzer
from localitylens.analysis.locality import LocalityAnalyzer
from localitylens.analysis.semantic_continuity import SemanticContinuityAnalyzer
from localitylens.analysis.thrashing import ThrashingAnalyzer
from localitylens.analysis.transition_graph import TransitionGraphAnalyzer
from localitylens.analysis.waste import WasteAnalyzer
from localitylens.core.metrics import AnalysisReport, MetricNames, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import EventKind, Trace, TraceEvent, TraceFormat

_T0 = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)


def _make_trace(targets: list[str], kind: EventKind = EventKind.FILE_READ) -> Trace:
    """Helper: build a Trace from a list of target file names."""
    return Trace(
        trace_id="test",
        source="test.json",
        format=TraceFormat.GENERIC_JSON,
        events=[
            TraceEvent(kind=kind, timestamp=_T0, target=t, sequence=i)
            for i, t in enumerate(targets)
        ],
    )


def _make_smap(targets: list[str]) -> SemanticMap:
    """Helper: build a SemanticMap with register_touch populated."""
    smap = SemanticMap(trace_id="test")

    for i, t in enumerate(targets):
        smap.register_touch(i, t)

    return smap


def _empty_smap() -> SemanticMap:
    return SemanticMap(trace_id="test")


# ---------------------------------------------------------------------------
# ChurnAnalyzer
# ---------------------------------------------------------------------------

class TestChurnAnalyzer:
    def test_basic_ratio(self):
        """3 reads + 1 write → ratio 0.25 → LOW."""
        analyzer = ChurnAnalyzer()
        report = AnalysisReport(trace_id="t")

        trace = _make_trace(
            ["a.py", "b.py", "a.py"],
            EventKind.FILE_READ,
        )

        trace.events.append(
            TraceEvent(
                kind=EventKind.FILE_WRITE,
                timestamp=_T0,
                target="a.py",
                sequence=3,
            )
        )

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.CHURN_RATIO)[0]

        assert m.value == pytest.approx(0.25)
        assert m.severity == Severity.LOW

    def test_all_writes_is_critical(self):
        analyzer = ChurnAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = _make_trace(
            ["a.py", "b.py", "c.py"],
            EventKind.FILE_WRITE,
        )

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.CHURN_RATIO)[0]

        assert m.value == pytest.approx(1.0)
        assert m.severity == Severity.CRITICAL

    def test_no_file_events_returns_zero(self):
        analyzer = ChurnAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = _make_trace(["bash"], EventKind.TOOL_CALL)

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.CHURN_RATIO)[0]

        assert m.value == 0.0
        assert m.severity == Severity.OK


# ---------------------------------------------------------------------------
# LocalityAnalyzer
# ---------------------------------------------------------------------------

class TestLocalityAnalyzer:
    def test_window_hits(self):
        """Sequence: main→utils→main→main. Expected 2/3 hits ≈ 0.6667 → LOW."""
        analyzer = LocalityAnalyzer()

        report = AnalysisReport(trace_id="t")

        smap = _make_smap(
            ["main.py", "utils.py", "main.py", "main.py"]
        )

        analyzer.analyze(
            Trace(
                trace_id="t",
                source="",
                format=TraceFormat.GENERIC_JSON,
            ),
            smap,
            report,
        )

        m = report.by_name(MetricNames.LOCALITY_SCORE)[0]

        assert m.value == pytest.approx(2 / 3, abs=1e-4)
        assert m.severity == Severity.LOW

    def test_single_event_returns_ok(self):
        analyzer = LocalityAnalyzer()

        report = AnalysisReport(trace_id="t")

        smap = _make_smap(["only.py"])

        analyzer.analyze(
            Trace(
                trace_id="t",
                source="",
                format=TraceFormat.GENERIC_JSON,
            ),
            smap,
            report,
        )

        m = report.by_name(MetricNames.LOCALITY_SCORE)[0]

        assert m.value == 1.0
        assert m.severity == Severity.OK

    def test_empty_smap_returns_ok(self):
        analyzer = LocalityAnalyzer()

        report = AnalysisReport(trace_id="t")

        analyzer.analyze(
            Trace(
                trace_id="t",
                source="",
                format=TraceFormat.GENERIC_JSON,
            ),
            _empty_smap(),
            report,
        )

        m = report.by_name(MetricNames.LOCALITY_SCORE)[0]

        assert m.value == 1.0


# ---------------------------------------------------------------------------
# ThrashingAnalyzer
# ---------------------------------------------------------------------------

class TestThrashingAnalyzer:
    def test_detects_abab_oscillation(self):
        """A→B→A→B pattern must produce at least 1 oscillation."""
        analyzer = ThrashingAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = _make_trace(
            ["a.py", "b.py", "a.py", "b.py", "a.py", "b.py"]
        )

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.OSCILLATION_THRASHING)[0]

        assert m.value >= 1.0
        assert m.extra["oscillations"] >= 1

    def test_no_oscillation_when_no_pattern(self):
        """Linear progression a→b→c→d should produce zero oscillations."""
        analyzer = ThrashingAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = _make_trace(
            ["a.py", "b.py", "c.py", "d.py", "e.py"]
        )

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.OSCILLATION_THRASHING)[0]

        assert m.value == 0.0
        assert m.severity == Severity.OK

    def test_short_trace_no_crash(self):
        """Fewer than 4 file events → no oscillation, no exception."""
        analyzer = ThrashingAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = _make_trace(["a.py", "b.py"])

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.OSCILLATION_THRASHING)[0]

        assert m.value == 0.0


# ---------------------------------------------------------------------------
# WasteAnalyzer
# ---------------------------------------------------------------------------

class TestWasteAnalyzer:
    def test_detects_idle_gap(self):
        """Gap of 45 s (> default 30 s threshold) → 1 gap, LOW severity."""
        analyzer = WasteAnalyzer()

        report = AnalysisReport(trace_id="t")

        t1 = _T0
        t2 = t1 + timedelta(seconds=45)

        trace = Trace(
            trace_id="t",
            source="test.json",
            format=TraceFormat.GENERIC_JSON,
            events=[
                TraceEvent(
                    kind=EventKind.TOOL_CALL,
                    timestamp=t1,
                    target="bash",
                    sequence=0,
                ),
                TraceEvent(
                    kind=EventKind.TOOL_CALL,
                    timestamp=t2,
                    target="bash",
                    sequence=1,
                ),
            ],
        )

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.WASTE_GAP_COUNT)[0]

        assert m.value == 1.0
        assert m.extra["total_waste_seconds"] == pytest.approx(45.0)
        assert m.severity == Severity.LOW

    def test_no_gap_below_threshold(self):
        """Gap of 10 s (< default 30 s) → 0 gaps."""
        analyzer = WasteAnalyzer()

        report = AnalysisReport(trace_id="t")

        t1 = _T0
        t2 = t1 + timedelta(seconds=10)

        trace = Trace(
            trace_id="t",
            source="test.json",
            format=TraceFormat.GENERIC_JSON,
            events=[
                TraceEvent(
                    kind=EventKind.TOOL_CALL,
                    timestamp=t1,
                    target="bash",
                    sequence=0,
                ),
                TraceEvent(
                    kind=EventKind.TOOL_CALL,
                    timestamp=t2,
                    target="bash",
                    sequence=1,
                ),
            ],
        )

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.WASTE_GAP_COUNT)[0]

        assert m.value == 0.0
        assert m.severity == Severity.OK

    def test_single_event_returns_ok(self):
        analyzer = WasteAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = _make_trace(["a.py"])

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.WASTE_GAP_COUNT)[0]

        assert m.value == 0.0


# ---------------------------------------------------------------------------
# AnomalyAnalyzer
# ---------------------------------------------------------------------------

class TestAnomalyAnalyzer:
    def test_oscillation_detected(self):
        """A→B→A→B should register as an oscillation anomaly."""
        analyzer = AnomalyAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = _make_trace(["a.py", "b.py", "a.py", "b.py"])

        analyzer.analyze(trace, _empty_smap(), report)

        assert any(
            a["type"] == "oscillation"
            for a in report.anomalies
        )

    def test_no_anomaly_on_clean_trace(self):
        """Linear trace with no patterns should score 0."""
        analyzer = AnomalyAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = _make_trace(["a.py", "b.py", "c.py"])

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.BEHAVIORAL_ANOMALIES)[0]

        assert m.value == 0.0
        assert m.severity == Severity.OK

    def test_severity_never_crashes(self):
        """High oscillation count must not raise AttributeError."""
        analyzer = AnomalyAnalyzer()

        report = AnalysisReport(trace_id="t")

        targets = ["a.py", "b.py"] * 30

        trace = _make_trace(targets)

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.BEHAVIORAL_ANOMALIES)[0]

        assert m.severity in list(Severity)


# ---------------------------------------------------------------------------
# ContextEntropyAnalyzer
# ---------------------------------------------------------------------------

class TestContextEntropyAnalyzer:
    def test_two_way_oscillation_has_high_entropy(self):
        """a→b→a→b creates two transition pairs and should score high entropy."""
        analyzer = ContextEntropyAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = _make_trace(
            [
                "a.py",
                "b.py",
                "a.py",
                "b.py",
                "a.py",
                "b.py",
            ]
        )

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.CONTEXT_ENTROPY)[0]

        assert m.value > 0.9

    def test_high_entropy_many_pairs(self):
        """Many distinct transitions → relative entropy near 1.0."""
        analyzer = ContextEntropyAnalyzer()

        report = AnalysisReport(trace_id="t")

        targets = [f"file_{i}.py" for i in range(9)]

        trace = _make_trace(targets)

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.CONTEXT_ENTROPY)[0]

        assert m.value >= 0.9
        assert m.severity in (
            Severity.HIGH,
            Severity.CRITICAL,
        )

    def test_no_transitions_returns_zero(self):
        """Single-event trace → no transitions → entropy 0."""
        analyzer = ContextEntropyAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = _make_trace(["a.py"])

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.CONTEXT_ENTROPY)[0]

        assert m.value == 0.0


# ---------------------------------------------------------------------------
# SemanticContinuityAnalyzer
# ---------------------------------------------------------------------------

class TestSemanticContinuityAnalyzer:
    def test_coherent_transitions_score_one(self):
        """All transitions stay in same directory."""
        analyzer = SemanticContinuityAnalyzer()

        report = AnalysisReport(trace_id="t")

        smap = SemanticMap(trace_id="t")

        smap.add_import("src/a.py", "src/b.py")

        smap.transitions = [
            ("src/a.py", "src/b.py"),
            ("src/b.py", "src/a.py"),
        ]

        trace = Trace(
            trace_id="t",
            source="",
            format=TraceFormat.GENERIC_JSON,
        )

        analyzer.analyze(trace, smap, report)

        m = report.by_name(MetricNames.SEMANTIC_CONTINUITY)[0]

        assert m.value == pytest.approx(1.0)
        assert m.severity == Severity.OK

    def test_no_transitions_returns_ok(self):
        analyzer = SemanticContinuityAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = Trace(
            trace_id="t",
            source="",
            format=TraceFormat.GENERIC_JSON,
        )

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.SEMANTIC_CONTINUITY)[0]

        assert m.value == 1.0
        assert m.severity == Severity.OK


# ---------------------------------------------------------------------------
# DependencyJumpAnalyzer
# ---------------------------------------------------------------------------

class TestDependencyJumpAnalyzer:
    def test_all_distant_jumps_are_critical(self):
        """Transitions between unrelated files."""
        analyzer = DependencyJumpAnalyzer()

        report = AnalysisReport(trace_id="t")

        smap = SemanticMap(trace_id="t")

        smap.transitions = [("a/foo.py", "z/bar.py")]

        trace = Trace(
            trace_id="t",
            source="",
            format=TraceFormat.GENERIC_JSON,
        )

        analyzer.analyze(trace, smap, report)

        m = report.by_name(MetricNames.DEPENDENCY_JUMP_RADIUS)[0]

        assert m.value == pytest.approx(2.0)
        assert m.severity == Severity.CRITICAL

    def test_direct_dependency_radius_is_one(self):
        analyzer = DependencyJumpAnalyzer()
        report = AnalysisReport(trace_id="t")
        smap = SemanticMap(trace_id="t")
        smap.register_touch(0, "src/a.py")
        smap.register_touch(1, "src/b.py")
        smap.add_import("src/a.py", "src/b.py")
        smap.transitions = [("src/a.py", "src/b.py")]

        trace = Trace(trace_id="t", source="", format=TraceFormat.GENERIC_JSON)

        analyzer.analyze(trace, smap, report)

        m = report.by_name(MetricNames.DEPENDENCY_JUMP_RADIUS)[0]

        assert m.value == pytest.approx(1.0)
        assert m.severity == Severity.OK

    def test_no_transitions_returns_ok(self):
        analyzer = DependencyJumpAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = Trace(
            trace_id="t",
            source="",
            format=TraceFormat.GENERIC_JSON,
        )

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.DEPENDENCY_JUMP_RADIUS)[0]

        assert m.value == 0.0
        assert m.severity == Severity.OK


# ---------------------------------------------------------------------------
# TransitionGraphAnalyzer
# ---------------------------------------------------------------------------

class TestTransitionGraphAnalyzer:
    def test_single_dominant_pair_ratio(self):
        """a→b appears 3 times out of 5 total transitions = 0.6."""
        analyzer = TransitionGraphAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = _make_trace(
            [
                "a.py",
                "b.py",
                "a.py",
                "b.py",
                "a.py",
                "b.py",
            ]
        )

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.TRANSITION_CONCENTRATION)[0]

        assert m.value == pytest.approx(0.6, abs=1e-4)

    def test_uniform_scatter_is_critical(self):
        """All unique transitions."""
        analyzer = TransitionGraphAnalyzer()

        report = AnalysisReport(trace_id="t")

        trace = _make_trace(
            [f"file_{i}.py" for i in range(10)]
        )

        analyzer.analyze(trace, _empty_smap(), report)

        m = report.by_name(MetricNames.TRANSITION_CONCENTRATION)[0]

        assert m.value == pytest.approx(1 / 9, abs=1e-4)
        assert m.severity == Severity.MEDIUM
