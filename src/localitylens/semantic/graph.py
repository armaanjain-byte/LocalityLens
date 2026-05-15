"""Symbol dependency graph built with NetworkX."""

from __future__ import annotations

import networkx as nx

from localitylens.semantic.symbols import Symbol


class DependencyGraph:
    """Directed graph of symbol dependencies extracted from a trace.

    Nodes are :class:`~localitylens.semantic.symbols.Symbol` names.
    Edges represent "A depends on B" relationships observed during the trace.
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_symbol(self, symbol: Symbol) -> None:
        """Add *symbol* as a node, storing it as node data.

        Args:
            symbol: Symbol to register.
        """
        self._graph.add_node(symbol.name, symbol=symbol)

    def add_dependency(self, from_name: str, to_name: str) -> None:
        """Record that *from_name* depends on *to_name*.

        Args:
            from_name: Dependent symbol name.
            to_name: Dependency symbol name.
        """
        self._graph.add_edge(from_name, to_name)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def neighbours(self, name: str) -> list[str]:
        """Return direct dependencies of *name*.

        Args:
            name: Symbol name to query.

        Returns:
            List of symbol names that *name* directly depends on.
        """
        return list(self._graph.successors(name))

    def node_count(self) -> int:
        """Return the number of symbols in the graph."""
        return self._graph.number_of_nodes()

    def edge_count(self) -> int:
        """Return the number of dependency edges."""
        return self._graph.number_of_edges()

    def is_empty(self) -> bool:
        """Return ``True`` when the graph has no nodes."""
        return self._graph.number_of_nodes() == 0

    def raw(self) -> nx.DiGraph:
        """Expose the underlying NetworkX graph for advanced queries."""
        return self._graph