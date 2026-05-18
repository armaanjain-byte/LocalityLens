"""Semantic neighborhood and distance utilities."""

from __future__ import annotations

from collections import deque

from localitylens.core.semantic_map import SemanticMap


class SemanticNeighborhoods:
    """Compute semantic proximity across symbols, files, and modules."""

    def __init__(self, smap: SemanticMap) -> None:
        self.smap = smap

    def file_distance(self, source: str, target: str, max_hops: int | None = None) -> int | None:
        """Return shortest semantic file distance, or None when disconnected."""
        return self._distance(self._file_graph(), source, target, max_hops=max_hops)

    def symbol_distance(self, source: str, target: str, max_hops: int | None = None) -> int | None:
        """Return shortest semantic symbol distance, or None when disconnected."""
        return self._distance(self._symbol_graph(), source, target, max_hops=max_hops)

    def module_distance(self, source: str, target: str, max_hops: int | None = None) -> int | None:
        """Return shortest module distance through imports."""
        return self._distance(self._module_graph(), source, target, max_hops=max_hops)

    def neighborhood_for_file(self, path: str, radius: int = 1) -> set[str]:
        """Return files within a semantic radius of the given file."""
        graph = self._file_graph()
        distances = self._distances(graph, path, max_hops=radius)
        return set(distances)

    def _file_graph(self) -> dict[str, set[str]]:
        graph = self.smap.dependency_graph()
        for path in self.smap.files:
            graph.setdefault(path, set()).update(self.smap.semantic_neighbors(path))
        for src, targets in list(graph.items()):
            for dst in targets:
                graph.setdefault(dst, set()).add(src)
        return graph

    def _symbol_graph(self) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = {
            symbol: set() for symbol in self.smap.definitions_by_symbol
        }
        for caller, callees in self.smap.call_graph.items():
            graph.setdefault(caller, set()).update(callees)
            for callee in callees:
                graph.setdefault(callee, set()).add(caller)
        for owner, references in self.smap.references_by_symbol.items():
            graph.setdefault(owner, set())
            for reference in references:
                if reference.scope:
                    graph.setdefault(reference.scope, set()).add(owner)
                    graph.setdefault(owner, set()).add(reference.scope)
        return graph

    def _module_graph(self) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = {}
        for src, targets in self.smap.imports.items():
            src_module = self._module_for_file(src)
            graph.setdefault(src_module, set())
            for target in targets:
                dst_module = self._module_for_file(target)
                graph[src_module].add(dst_module)
                graph.setdefault(dst_module, set()).add(src_module)
        return graph

    @staticmethod
    def _module_for_file(path: str) -> str:
        return path.rsplit(".", 1)[0].replace("/", ".").replace("\\", ".")

    @staticmethod
    def _distance(
        graph: dict[str, set[str]],
        source: str,
        target: str,
        max_hops: int | None = None,
    ) -> int | None:
        return SemanticNeighborhoods._distances(graph, source, max_hops=max_hops).get(target)

    @staticmethod
    def _distances(
        graph: dict[str, set[str]],
        source: str,
        max_hops: int | None = None,
    ) -> dict[str, int]:
        if source not in graph:
            return {}

        distances = {source: 0}
        queue: deque[tuple[str, int]] = deque([(source, 0)])
        while queue:
            node, distance = queue.popleft()
            if max_hops is not None and distance >= max_hops:
                continue
            for neighbor in graph.get(node, set()):
                if neighbor not in distances:
                    distances[neighbor] = distance + 1
                    queue.append((neighbor, distance + 1))
        return distances
