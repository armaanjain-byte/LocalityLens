"""Maps raw trace events to semantic entities via cached, cross-platform tree-sitter walks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import EventKind, Trace
from localitylens.semantic.graph import DependencyGraph
from localitylens.semantic.symbols import Symbol, SymbolKind
from localitylens.utils.logger import get_logger

log = get_logger(__name__)
_FILE_KINDS = {EventKind.FILE_READ, EventKind.FILE_WRITE, EventKind.FILE_DELETE}

_TS_AVAILABLE = False
try:
    import tree_sitter
    import tree_sitter_python as ts_py
    _TS_AVAILABLE = True
except ImportError:
    log.warning("tree-sitter or target language packs not found. AST parsing disabled.")


class SemanticMapper:
    """Build a SemanticMap and handle dependency graph extraction passes with unified paths."""

    _MAX_FILE_BYTES = 1 * 1024 * 1024

    def __init__(self) -> None:
        # Finding 5: Cache the tree-sitter parser instance to stop O(N) allocation loops
        self._parser: tree_sitter.Parser | None = None

    def _get_parser(self) -> tree_sitter.Parser | None:
        """Lazy-init a single tree-sitter Parser instance, reused across all files."""
        if self._parser is None and _TS_AVAILABLE:
            try:
                self._parser = tree_sitter.Parser(tree_sitter.Language(ts_py.language()))
            except Exception as exc:
                log.debug("Failed to initialize tree-sitter parser: %s", exc)
        return self._parser

    def _normalise_path(self, path_str: str) -> str:
        """Finding 6: Convert OS backslashes to standard POSIX keys for cross-platform matching."""
        return Path(path_str).as_posix()

    def build(self, trace: Trace) -> SemanticMap:
        smap = SemanticMap(trace_id=trace.trace_id)
        for event in trace.events:
            if event.kind in _FILE_KINDS and event.target:
                # Finding 6: Normalise the input key immediately before registration
                norm_path = self._normalise_path(event.target)
                smap.register_touch(seq=event.sequence, path=norm_path)
                if norm_path in smap.files:
                    self._enrich_file_symbols(norm_path, smap.files[norm_path])
        return smap

    def build_graph(self, trace: Trace) -> DependencyGraph:
        graph = DependencyGraph()
        for event in trace.events:
            if event.kind is EventKind.SYMBOL_LOOKUP and event.target:
                file_metadata = event.metadata.get("file", "")
                norm_file = self._normalise_path(file_metadata) if file_metadata else ""
                sym = Symbol(
                    name=event.target,
                    kind=SymbolKind.UNKNOWN,
                    file_path=norm_file,
                )
                graph.add_symbol(sym)
                dep = event.metadata.get("depends_on")
                if dep:
                    graph.add_dependency(event.target, dep)

        unique_files = {self._normalise_path(e.target) for e in trace.events if e.kind in _FILE_KINDS and e.target}
        for file_str in unique_files:
            self._extract_dependencies_from_file(file_str, graph)
        return graph

    def _enrich_file_symbols(self, path_str: str, file_node: Any) -> None:
        parser = self._get_parser()
        if not parser:
            return
        path = Path(path_str)
        if not path.is_file() or path.suffix != ".py":
            return

        try:
            if path.stat().st_size > self._MAX_FILE_BYTES:
                return
            content = path.read_bytes()
            tree = parser.parse(content)

            stack = [tree.root_node]
            while stack:
                node = stack.pop()
                if node.type in ("function_definition", "class_definition"):
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        name_str = content[name_node.start_byte : name_node.end_byte].decode(
                            "utf-8", errors="ignore"
                        )
                        if name_str not in file_node.symbol_names:
                            file_node.symbol_names.append(name_str)
                stack.extend(node.children)
        except Exception as exc:
            log.debug("AST parse failed for %s: %s", path_str, exc)

    def _extract_dependencies_from_file(self, path_str: str, graph: DependencyGraph) -> None:
        parser = self._get_parser()
        if not parser:
            return
        path = Path(path_str)
        if not path.is_file() or path.suffix != ".py":
            return

        try:
            if path.stat().st_size > self._MAX_FILE_BYTES:
                return
            content = path.read_bytes()
            tree = parser.parse(content)

            stack = [tree.root_node]
            while stack:
                node = stack.pop()
                if node.type in ("import_statement", "import_from_statement"):
                    import_text = content[node.start_byte : node.end_byte].decode(
                        "utf-8", errors="ignore"
                    )
                    graph.add_dependency(path_str, import_text.strip())
                stack.extend(node.children)
        except Exception:
            pass