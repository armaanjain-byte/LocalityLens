"""Integration tests for the full analysis pipeline."""

from __future__ import annotations

from pathlib import Path

from localitylens.cli.commands.analyze import ANALYZERS
from localitylens.core.metrics import AnalysisReport
from localitylens.parsers.claude_code import ClaudeCodeParser
from localitylens.semantic.mapper import SemanticMapper
from localitylens.storage.db import ReportStore


def test_full_pipeline_on_sample_trace(tmp_path):
    trace_file = Path("my_trace.jsonl")
    parser = ClaudeCodeParser()
    trace = parser.parse(trace_file)
    smap = SemanticMapper().build(trace)
    report = AnalysisReport(trace_id=trace.trace_id)

    for analyzer in ANALYZERS:
        analyzer.analyze(trace, smap, report)

    store = ReportStore(tmp_path / "test.db")
    store.save(report)
    loaded = store.load(report.trace_id)

    assert loaded is not None
    assert {m.name for m in loaded.metrics} == {m.name for m in report.metrics}
    assert loaded.anomalies == report.anomalies
