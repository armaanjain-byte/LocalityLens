"""Unit tests for the tree-sitter AST-aware semantic mapping engine."""

from pathlib import Path
import pytest

from localitylens.core.trace import EventKind, Trace, TraceEvent, TraceFormat
from localitylens.semantic.mapper import SemanticMapper


def test_semantic_mapper_ast_enrichment_graceful_fallback():
    """Ensure the mapper handles missing files or environment constraints gracefully without throwing errors."""
    mapper = SemanticMapper()
    
    # Trace referencing a non-existent python file
    trace = Trace(
        trace_id="test_ast_fallback",
        source="trace.json",
        format=TraceFormat.GENERIC_JSON,
        events=[
            TraceEvent(kind=EventKind.FILE_READ, timestamp=None, target="non_existent_file.py", sequence=0)
        ]
    )
    
    smap = mapper.build(trace)
    assert "non_existent_file.py" in smap.files
    # Should safely remain empty since the file does not exist on disk to be parsed
    assert smap.files["non_existent_file.py"].symbol_names == []


def test_build_graph_empty_by_default():
    """Verify that a trace with no symbol lookup events creates an empty dependency graph profile."""
    mapper = SemanticMapper()
    trace = Trace(
        trace_id="test_graph_empty",
        source="trace.json",
        format=TraceFormat.GENERIC_JSON,
        events=[
            TraceEvent(kind=EventKind.FILE_READ, timestamp=None, target="main.py", sequence=0)
        ]
    )
    
    graph = mapper.build_graph(trace)
    assert graph.is_empty() or graph.node_count() == 0