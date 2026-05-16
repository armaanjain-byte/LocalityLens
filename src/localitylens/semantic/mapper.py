"""Maps raw trace events to semantic entities via stack-based tree-sitter walks."""

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

# M-7: Check tool presence and isolate bindings safely
_TS_AVAILABLE = False
try:
    import tree_sitter
    import tree_sitter_python as ts_py
    _TS_AVAILABLE = True
except ImportError:
    log.warning("tree-sitter or target language packs not found. AST parsing disabled.")


class SemanticMapper:
    """Build a SemanticMap and handle dependency graph extraction passes."""

    _MAX_FILE_BYTES = 1 * 1024 * 1024  # 1MB size threshold protection cap

    def build(self, trace: Trace) -> SemanticMap:
        smap = SemanticMap(trace_id=trace.trace_id)
        for event in trace.events:
            if event.kind in _FILE_KINDS and event.target:
                smap.register_touch(seq=event.sequence, path=event.target)
                if event.target in smap.files:
                    self._enrich_file_symbols(event.target, smap.files[event.target])
        return smap

    def build_graph(self, trace: Trace) -> DependencyGraph:
        graph = DependencyGraph()
        for event in trace.events:
            if event.kind is EventKind.SYMBOL_LOOKUP and event.target:
                sym = Symbol(
                    name=event.target,
                    kind=SymbolKind.UNKNOWN,
                    file_path=event.metadata.get("file", ""),
                )
                graph.add_symbol(sym)
                dep = event.metadata.get("depends_on")
                if dep:
                    graph.add_dependency(event.target, dep)

        # M-7: Automate edge resolution by analyzing active file dependencies
        unique_files = {e.target for e in trace.events if e.kind in _FILE_KINDS and e.target}
        for file_str in unique_files:
            self._extract_dependencies_from_file(file_str, graph)
        return graph

    # M-7: Iterative loop structure bypasses recursion depth limit risks completely
    def _enrich_file_symbols(self, path_str: str, file_node: Any) -> None:
        if not _TS_AVAILABLE:
            return
        path = Path(path_str)
        if not path.is_file() or path.suffix != ".py":
            return

        try:
            if path.stat().st_size > self._MAX_FILE_BYTES:
                return
            content = path.read_bytes()
            parser = tree_sitter.Parser(tree_sitter.Language(ts_py.language()))
            tree = parser.parse(content)

            # Iterative explicit array stack traversal
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
        if not _TS_AVAILABLE:
            return
        path = Path(path_str)
        if not path.is_file() or path.suffix != ".py":
            return

        try:
            if path.stat().st_size > self._MAX_FILE_BYTES:
                return
            content = path.read_bytes()
            parser = tree_sitter.Parser(tree_sitter.Language(ts_py.language()))
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