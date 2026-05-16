"""Unit tests for LocalityLens stateless analysis engines."""

from datetime import datetime, timedelta
import pytest

from localitylens.analysis.churn import ChurnAnalyzer
from localitylens.analysis.locality import LocalityAnalyzer
from localitylens.analysis.thrashing import ThrashingAnalyzer
from localitylens.analysis.waste import WasteAnalyzer
from localitylens.core.metrics import AnalysisReport, Severity
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import EventKind, Trace, TraceEvent, TraceFormat


@pytest.fixture
def base_timestamp() -> datetime:
    """Provides a stable baseline timestamp for events."""
    return datetime(2026, 5, 16, 12, 0, 0)


def test_churn_analyzer_calculation(base_timestamp):
    """Verify write churn calculations and severity classification."""
    analyzer = ChurnAnalyzer()
    report = AnalysisReport(trace_id="test_churn")
    
    # 3 reads, 1 write -> total 4 events. Churn ratio = 1/4 = 0.25
    trace = Trace(
        trace_id="test_churn",
        source="test.json",
        format=TraceFormat.GENERIC_JSON,
        events=[
            TraceEvent(kind=EventKind.FILE_READ, timestamp=base_timestamp, target="a.py", sequence=0),
            TraceEvent(kind=EventKind.FILE_READ, timestamp=base_timestamp, target="b.py", sequence=1),
            TraceEvent(kind=EventKind.FILE_READ, timestamp=base_timestamp, target="a.py", sequence=2),
            TraceEvent(kind=EventKind.FILE_WRITE, timestamp=base_timestamp, target="a.py", sequence=3),
        ]
    )
    
    analyzer.analyze(trace, report)
    
    metric = report.by_name("churn_ratio")[0]
    assert metric.value == 0.25
    assert metric.severity == Severity.LOW  # 0.25 is <= limit (0.4)


def test_locality_analyzer_sequence(base_timestamp):
    """Verify contextual sliding window locality hits."""
    analyzer = LocalityAnalyzer()
    report = AnalysisReport(trace_id="test_locality")
    
    smap = SemanticMap(trace_id="test_locality")
    # Transitions:
    # 0 -> 1: "main.py" -> "utils.py" (not in window context) -> Miss
    # 1 -> 2: "utils.py" -> "main.py" (is in window context ["main.py", "utils.py"]) -> Hit
    # 2 -> 3: "main.py" -> "main.py" (is in window context) -> Hit
    smap.register_touch(0, "main.py")
    smap.register_touch(1, "utils.py")
    smap.register_touch(2, "main.py")
    smap.register_touch(3, "main.py")
    
    analyzer.analyze(smap, report)
    
    metric = report.by_name("locality_score")[0]
    assert metric.value == pytest.approx(2 / 3,abs=1e-4) # 2 hits out of 3 transitions
    assert metric.severity == Severity.LOW


def test_thrashing_analyzer_repeats():
    """Verify detection of highly repetitive file revisit counts."""
    analyzer = ThrashingAnalyzer()
    report = AnalysisReport(trace_id="test_thrash")
    
    smap = SemanticMap(trace_id="test_thrash")
    # Revisit file 'loop.py' 4 times (exceeds default limit of 3)
    smap.register_touch(0, "loop.py")
    smap.register_touch(1, "other.py")
    smap.register_touch(2, "loop.py")
    smap.register_touch(3, "loop.py")
    smap.register_touch(4, "loop.py")
    
    analyzer.analyze(smap, report)
    
    metric = report.by_name("thrash_file_count")[0]
    assert metric.value == 1.0  # 1 file is thrashing
    assert "loop.py" in metric.extra["thrashing_files"]
    assert metric.severity == Severity.CRITICAL


def test_waste_analyzer_idle_gaps(base_timestamp):
    """Verify detection of idle periods exceeding waste thresholds."""
    analyzer = WasteAnalyzer()
    report = AnalysisReport(trace_id="test_waste")
    
    # Create an idle gap of 45 seconds (default threshold is 30s)
    t1 = base_timestamp
    t2 = t1 + timedelta(seconds=45)
    
    trace = Trace(
        trace_id="test_waste",
        source="test.json",
        format=TraceFormat.GENERIC_JSON,
        events=[
            TraceEvent(kind=EventKind.TOOL_CALL, timestamp=t1, target="bash", sequence=0),
            TraceEvent(kind=EventKind.TOOL_CALL, timestamp=t2, target="bash", sequence=1),
        ]
    )
    
    analyzer.analyze(trace, report)
    
    metric = report.by_name("waste_gap_count")[0]
    assert metric.value == 1.0
    assert metric.extra["total_waste_seconds"] == 45.0
    assert metric.severity == Severity.LOW