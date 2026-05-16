"""Maps raw trace events to semantic entities (files, symbols, graph) via tree-sitter AST parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import EventKind, Trace
from localitylens.semantic.graph import DependencyGraph
from localitylens.semantic.symbols import Symbol, SymbolKind
from localitylens.utils.logger import get_logger

log = get_logger(__name__)

# Event kinds that represent meaningful file access.
_FILE_KINDS = {EventKind.FILE_READ, EventKind.FILE_WRITE, EventKind.FILE_DELETE}


class SemanticMapper:
    """Build a :class:`~localitylens.core.semantic_map.SemanticMap` from a
    :class:`~localitylens.core.trace.Trace`.

    This module performs AST-aware code intelligence using tree-sitter to
    extract defined symbols and module dependencies from files accessed during the session.
    """

    def build(self, trace: Trace) -> SemanticMap:
        """Build and return a :class:`SemanticMap` for *trace*.

        Args:
            trace: Fully parsed trace.

        Returns:
            Populated :class:`SemanticMap`.
        """
        smap = SemanticMap(trace_id=trace.trace_id)

        for event in trace.events:
            if event.kind in _FILE_KINDS and event.target:
                smap.register_touch(seq=event.sequence, path=event.target)
                # Enrich file nodes with actual AST symbol names if the file exists locally
                if event.target in smap.files:
                    self._enrich_file_symbols(event.target, smap.files[event.target])

        log.debug(
            "SemanticMap for %s: %d unique files touched",
            trace.trace_id,
            len(smap.files),
        )
        return smap

    def build_graph(self, trace: Trace) -> DependencyGraph:
        """Build a basic dependency graph from symbol-lookup events and file imports.

        Args:
            trace: Fully parsed trace.

        Returns:
            :class:`DependencyGraph` populated with explicit and extracted relationships.
        """
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

        # Automated fall-back: Scan files touched in the trace for imports to map file-level dependencies
        unique_files = {e.target for e in trace.events if e.kind in _FILE_KINDS and e.target}
        for file_str in unique_files:
            self._extract_dependencies_from_file(file_str, graph)

        return graph

    # ------------------------------------------------------------------
    # Private AST Parsing Helpers
    # ------------------------------------------------------------------

    def _enrich_file_symbols(self, path_str: str, file_node: Any) -> None:
        """Open a local source file and extract its symbols using tree-sitter traversal."""
        path = Path(path_str)
        if not path.is_file() or path.suffix != ".py":
            return

        try:
            content = path.read_bytes()
            from tree_sitter import Language, Parser
            try:
                import tree_sitter_python as ts_py
                lang = Language(ts_py.language())
                parser = Parser(lang)
                tree = parser.parse(content)
                self._extract_symbols_from_node(tree.root_node, content, file_node)
            except ImportError:
                log.debug("tree-sitter-python package not found. Skipping deep AST parsing for %s.", path_str)
        except Exception as e:
            log.warning("Failed to perform tree-sitter AST parse on %s: %s", path_str, e)

    def _extract_symbols_from_node(self, node: Any, content: bytes, file_node: Any) -> None:
        """Recursively traverse AST nodes to extract function and class declarations."""
        if node.type in ("function_definition", "class_definition"):
            name_node = node.child_by_field_name("name")
            if name_node:
                try:
                    name_str = content[name_node.start_byte : name_node.end_byte].decode("utf-8")
                    if name_str not in file_node.symbol_names:
                        file_node.symbol_names.append(name_str)
                except Exception:
                    pass

        for child in node.children:
            self._extract_symbols_from_node(child, content, file_node)

    def _extract_dependencies_from_file(self, path_str: str, graph: DependencyGraph) -> None:
        """Scan a source file to extract internal import module relationships into the dependency graph."""
        path = Path(path_str)
        if not path.is_file() or path.suffix != ".py":
            return

        try:
            content = path.read_bytes()
            from tree_sitter import Language, Parser
            import tree_sitter_python as ts_py
            lang = Language(ts_py.language())
            parser = Parser(lang)
            tree = parser.parse(content)
            self._extract_imports_from_node(tree.root_node, content, path_str, graph)
        except Exception:
            pass

    def _extract_imports_from_node(self, node: Any, content: bytes, current_file: str, graph: DependencyGraph) -> None:
        """Locate import AST nodes and append them as graph edges."""
        if node.type in ("import_statement", "import_from_statement"):
            try:
                import_text = content[node.start_byte : node.end_byte].decode("utf-8")
                graph.add_dependency(current_file, import_text.strip())
            except Exception:
                pass

        for child in node.children:
            self._extract_imports_from_node(child, content, current_file, graph)