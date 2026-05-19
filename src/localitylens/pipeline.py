"""Programmatic analysis pipeline for traces and repositories."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from localitylens.analysis.anomaly import AnomalyAnalyzer
from localitylens.analysis.churn import ChurnAnalyzer
from localitylens.analysis.context_entropy import ContextEntropyAnalyzer
from localitylens.analysis.cognitive_load import CognitiveLoadAnalyzer
from localitylens.analysis.dependency_jump import DependencyJumpAnalyzer
from localitylens.analysis.locality import LocalityAnalyzer
from localitylens.analysis.retrieval_pressure import RetrievalPressureAnalyzer
from localitylens.analysis.semantic_continuity import SemanticContinuityAnalyzer
from localitylens.analysis.semantic_drift import SemanticDriftAnalyzer
from localitylens.analysis.thrashing import ThrashingAnalyzer
from localitylens.analysis.transition_graph import TransitionGraphAnalyzer
from localitylens.analysis.waste import WasteAnalyzer
from localitylens.core.exceptions import UnsupportedFormatError
from localitylens.core.metrics import AnalysisReport
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.parsers.claude_code import ClaudeCodeParser
from localitylens.parsers.generic_json import GenericJsonParser
from localitylens.semantic.mapper import SemanticMapper


class Analyzer(Protocol):
    """Shared analyzer protocol."""

    def analyze(self, trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None:
        """Append metric results to report."""

PARSERS = [ClaudeCodeParser(), GenericJsonParser()]

ANALYZER_REGISTRY: list[Analyzer] = [
    AnomalyAnalyzer(),
    SemanticContinuityAnalyzer(),
    DependencyJumpAnalyzer(),
    ContextEntropyAnalyzer(),
    TransitionGraphAnalyzer(),
    ChurnAnalyzer(),
    ThrashingAnalyzer(),
    SemanticDriftAnalyzer(),
    RetrievalPressureAnalyzer(),
    CognitiveLoadAnalyzer(),
    WasteAnalyzer(),
    LocalityAnalyzer(),
]


def parse_trace(trace_path: Path) -> Trace:
    """Parse a trace with the first matching parser."""
    parser = next((p for p in PARSERS if p.can_parse(trace_path)), None)
    if not parser:
        raise UnsupportedFormatError(f"No parser found for file: {trace_path.name}")
    return parser.parse(trace_path)


def run_pipeline(trace_path: Path, repo_path: Path | None = None) -> AnalysisReport:
    """Parse, semantically map, and analyze a trace."""
    trace = parse_trace(trace_path)
    smap = build_semantic_map(trace, repo_path=repo_path)
    return analyze_trace(trace, smap)


def build_semantic_map(trace: Trace, repo_path: Path | None = None) -> SemanticMap:
    """Build repository-aware semantics for a parsed trace."""
    return SemanticMapper().build(trace, repo_path=repo_path)


def analyze_trace(trace: Trace, smap: SemanticMap) -> AnalysisReport:
    """Run all registered analyzers over a trace and semantic map."""
    report = AnalysisReport(trace_id=trace.trace_id)
    for analyzer in ANALYZER_REGISTRY:
        analyzer.analyze(trace, smap, report)
    report.sort_metrics()
    return report
