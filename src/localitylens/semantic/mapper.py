"""Maps raw trace events to semantic entities (files, symbols, graph)."""

from __future__ import annotations

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

    This is the entry point for the semantic layer. It is intentionally
    simple: it indexes file touches and extracts symbols from event targets
    without running a full tree-sitter parse (that is reserved for future
    enrichment).
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

        log.debug(
            "SemanticMap for %s: %d unique files touched",
            trace.trace_id,
            len(smap.files),
        )
        return smap

    def build_graph(self, trace: Trace) -> DependencyGraph:
        """Build a basic dependency graph from symbol-lookup events.

        Currently adds one node per unique SYMBOL_LOOKUP target; edges are
        added only when the metadata contains an ``"depends_on"`` key.

        Args:
            trace: Fully parsed trace.

        Returns:
            :class:`DependencyGraph` (may be empty for traces without
            symbol-lookup events).
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

        return graph