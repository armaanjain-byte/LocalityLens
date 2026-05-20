"""Unit tests for the semantic mapping engine."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import EventKind, Trace, TraceEvent, TraceFormat
from localitylens.semantic.context_window import ContextWindowSimulator
from localitylens.semantic.mapper import SemanticMapper
from localitylens.semantic.neighborhoods import SemanticNeighborhoods
from localitylens.semantic.repository_indexer import RepositoryIndexer

_T0 = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)


def _make_trace(targets: list[str], kind: EventKind = EventKind.FILE_READ) -> Trace:
    return Trace(
        trace_id="test",
        source="trace.json",
        format=TraceFormat.GENERIC_JSON,
        events=[
            TraceEvent(kind=kind, timestamp=_T0, target=t, sequence=i)
            for i, t in enumerate(targets)
        ],
    )


class TestSemanticMapper:
    def test_build_populates_files(self):
        """Every file target in the trace must appear in smap.files."""
        mapper = SemanticMapper()
        trace = _make_trace(["src/a.py", "src/b.py", "tests/test_a.py"])
        smap = mapper.build(trace)
        assert "src/a.py" in smap.files
        assert "src/b.py" in smap.files
        assert "tests/test_a.py" in smap.files

    def test_build_populates_touch_sequence(self):
        """touch_sequence() must return targets in event order."""
        mapper = SemanticMapper()
        trace = _make_trace(["a.py", "b.py", "c.py"])
        smap = mapper.build(trace)
        assert smap.touch_sequence() == ["a.py", "b.py", "c.py"]

    def test_build_constructs_transitions(self):
        """Consecutive distinct targets become transition pairs."""
        mapper = SemanticMapper()
        trace = _make_trace(["a.py", "b.py", "c.py"])
        smap = mapper.build(trace)
        assert ("a.py", "b.py") in smap.transitions
        assert ("b.py", "c.py") in smap.transitions

    def test_no_self_transitions(self):
        """Consecutive identical targets must NOT produce a transition."""
        mapper = SemanticMapper()
        trace = _make_trace(["a.py", "a.py", "b.py"])
        smap = mapper.build(trace)
        assert ("a.py", "a.py") not in smap.transitions
        assert ("a.py", "b.py") in smap.transitions

    def test_same_directory_files_are_neighbors_not_imports(self):
        """Same-directory adjacency must not be mislabeled as imports."""
        mapper = SemanticMapper()
        trace = _make_trace(["src/a.py", "src/b.py"])
        smap = mapper.build(trace)
        assert "src/b.py" in smap.neighbors.get("src/a.py", set())
        assert "src/a.py" in smap.neighbors.get("src/b.py", set())
        assert "src/b.py" not in smap.imports.get("src/a.py", set())
        assert "src/a.py" not in smap.imports.get("src/b.py", set())

    def test_ast_imports_populate_reverse_imports(self, tmp_path):
        mapper = SemanticMapper()
        package = tmp_path / "pkg"
        package.mkdir()
        (package / "a.py").write_text("from pkg import b\n\nclass A:\n    pass\n", encoding="utf-8")
        (package / "b.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
        trace = _make_trace(["pkg/a.py", "pkg/b.py"])
        trace.source = str(tmp_path / "trace.json")

        smap = mapper.build(trace)

        assert "pkg/b.py" in smap.imports.get("pkg/a.py", set())
        assert "pkg/a.py" in smap.reverse_imports.get("pkg/b.py", set())
        assert smap.files["pkg/a.py"].symbol_names == ["pkg.a.A"]
        assert smap.symbols["pkg.a.A"].line == 3

    def test_ast_symbol_index_includes_methods_and_short_names(self, tmp_path):
        mapper = SemanticMapper()
        package = tmp_path / "pkg"
        package.mkdir()
        (package / "a.py").write_text(
            "def top():\n    pass\n\nclass A:\n    def method(self):\n        pass\n",
            encoding="utf-8",
        )
        trace = _make_trace(["pkg/a.py"])
        trace.source = str(tmp_path / "trace.json")

        smap = mapper.build(trace)

        assert "pkg.a.top" in smap.symbols
        assert "pkg.a.A" in smap.symbols
        assert "pkg.a.A.method" in smap.symbols
        assert smap.symbols["method"].file_path == "pkg/a.py"

    def test_ast_references_and_call_graph_are_indexed(self, tmp_path):
        mapper = SemanticMapper()
        package = tmp_path / "pkg"
        package.mkdir()
        (package / "a.py").write_text(
            "from pkg.b import helper\n\n"
            "def run():\n"
            "    return helper()\n",
            encoding="utf-8",
        )
        (package / "b.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
        trace = _make_trace(["pkg/a.py", "pkg/b.py"])
        trace.source = str(tmp_path / "trace.json")

        smap = mapper.build(trace)

        assert "helper" in smap.symbol_references
        assert "pkg.b.helper" in smap.call_graph["pkg.a.run"]
        assert smap.calls_by_symbol["pkg.a.run"][0].resolved_symbol == "pkg.b.helper"
        assert smap.owners_by_reference[smap.symbol_references["helper"][0]] == "pkg.b.helper"
        assert "pkg/b.py" in smap.semantic_neighbors("pkg/a.py")

    def test_repository_first_indexing_includes_untouched_files(self, tmp_path):
        mapper = SemanticMapper()
        repo = tmp_path / "repo"
        package = repo / "pkg"
        package.mkdir(parents=True)
        (package / "a.py").write_text("from pkg import b\n", encoding="utf-8")
        (package / "b.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
        trace = _make_trace(["pkg/a.py"])
        trace.source = str(tmp_path / "trace.json")

        smap = mapper.build(trace, repo_path=repo)

        assert "pkg/b.py" in smap.files
        assert "pkg/b.py" in smap.imports["pkg/a.py"]
        assert "pkg.b.helper" in smap.symbol_definitions

    def test_ignored_targets_excluded(self):
        """session, unknown_file, search_operation must not appear in transitions or files."""
        mapper = SemanticMapper()
        trace = _make_trace(["session", "unknown_file", "search_operation", "real.py"])
        smap = mapper.build(trace)
        assert "session" not in smap.files
        assert "unknown_file" not in smap.files
        assert "search_operation" not in smap.files
        # Only real.py should be in files
        assert "real.py" in smap.files

    def test_empty_trace_produces_empty_smap(self):
        """A trace with no events must produce an empty SemanticMap without error."""
        mapper = SemanticMapper()
        trace = Trace(trace_id="empty", source="t.json", format=TraceFormat.GENERIC_JSON)
        smap = mapper.build(trace)
        assert smap.files == {}
        assert smap.transitions == []
        assert smap.touch_sequence() == []

    def test_non_existent_file_handled_gracefully(self):
        """
        A trace referencing a file that doesn't exist on disk must not raise.
        The mapper registers it as a file node with no symbol_names.
        """
        mapper = SemanticMapper()
        trace = _make_trace(["non_existent_file.py"])
        smap = mapper.build(trace)
        assert "non_existent_file.py" in smap.files
        assert smap.files["non_existent_file.py"].symbol_names == []

    def test_duplicate_sequence_is_skipped_without_crashing(self):
        mapper = SemanticMapper()
        trace = Trace(
            trace_id="test",
            source="trace.json",
            format=TraceFormat.GENERIC_JSON,
            events=[
                TraceEvent(kind=EventKind.FILE_READ, timestamp=_T0, target="a.py", sequence=0),
                TraceEvent(kind=EventKind.FILE_READ, timestamp=_T0, target="b.py", sequence=0),
                TraceEvent(kind=EventKind.FILE_READ, timestamp=_T0, target="c.py", sequence=1),
            ],
        )

        smap = mapper.build(trace)

        assert smap.touch_sequence() == ["a.py", "c.py"]
        assert ("b.py", "c.py") not in smap.transitions

    def test_syntax_error_file_does_not_crash_mapper(self, tmp_path):
        package = tmp_path / "pkg"
        package.mkdir()
        (package / "broken.py").write_text("def nope(:\n", encoding="utf-8")
        trace = _make_trace(["pkg/broken.py"])
        trace.source = str(tmp_path / "trace.json")

        smap = SemanticMapper().build(trace)

        assert "pkg/broken.py" in smap.files

    def test_module_index_prefers_longer_path_on_basename_collision(self):
        index = RepositoryIndexer._module_index({"src/utils.py", "tests/helpers/utils.py"})

        assert index["utils"] == "tests/helpers/utils.py"

    def test_repository_indexer_crawls_supported_source_extensions(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        for name in ("a.py", "b.ts", "c.tsx", "d.js", "e.rs", "f.go"):
            (repo / name).write_text("", encoding="utf-8")

        files = RepositoryIndexer().crawl(repo)

        assert files == {"a.py", "b.ts", "c.tsx", "d.js", "e.rs", "f.go"}

    def test_semantic_neighborhood_distance_uses_call_graph(self, tmp_path):
        mapper = SemanticMapper()
        package = tmp_path / "pkg"
        package.mkdir()
        (package / "a.py").write_text(
            "from pkg.b import helper\n\n"
            "def run():\n"
            "    return helper()\n",
            encoding="utf-8",
        )
        (package / "b.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
        trace = _make_trace(["pkg/a.py", "pkg/b.py"])
        trace.source = str(tmp_path / "trace.json")
        smap = mapper.build(trace)

        neighborhoods = SemanticNeighborhoods(smap)

        assert neighborhoods.symbol_distance("pkg.a.run", "pkg.b.helper") == 1
        assert neighborhoods.file_distance("pkg/a.py", "pkg/b.py") == 1

    def test_context_window_simulates_eviction_and_reload(self):
        state = ContextWindowSimulator(capacity=2).simulate(["a", "b", "c", "a"])

        assert state.eviction_count == 2
        assert state.reload_count == 1
        assert list(state.active) == ["c", "a"]


class TestSemanticMapRegisterTouch:
    def test_register_touch_increments_count(self):
        smap = SemanticMap(trace_id="t")
        smap.register_touch(0, "a.py")
        smap.register_touch(1, "a.py")
        assert smap.files["a.py"].touch_count == 2

    def test_register_touch_sequence_conflict_raises(self):
        """Same sequence number with different paths must raise ValueError."""
        smap = SemanticMap(trace_id="t")
        smap.register_touch(0, "a.py")
        with pytest.raises(ValueError, match="Conflicting paths"):
            smap.register_touch(0, "b.py")

    def test_register_touch_same_seq_same_path_is_idempotent(self):
        """Same sequence number + same path must not raise or double-count."""
        smap = SemanticMap(trace_id="t")
        smap.register_touch(0, "a.py")
        smap.register_touch(0, "a.py")  # should not raise
        assert smap.files["a.py"].touch_count == 1

    def test_touch_sequence_cache_invalidated_on_new_touch(self):
        smap = SemanticMap(trace_id="t")
        smap.register_touch(0, "a.py")
        _ = smap.touch_sequence()  # populate cache
        smap.register_touch(1, "b.py")  # must invalidate cache
        assert smap.touch_sequence() == ["a.py", "b.py"]
