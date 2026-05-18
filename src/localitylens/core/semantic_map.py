"""Semantic map indexers with memoization caching optimization."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from localitylens.semantic.symbols import Symbol


@dataclass
class FileNode:
    """A source file referenced in a trace."""

    path: str
    touch_count: int = 0
    symbol_names: list[str] = field(default_factory=list)


@dataclass
class SemanticMap:
    """
    Holds all semantic relationships extracted from a single Trace.

    Built exclusively by SemanticMapper.build() — do not construct manually
    outside of tests.

    Key invariants:
    - Every key in event_file_index also appears in files.
    - Every entry in imports[src] also appears in reverse_imports[dst] (enforced by add_import).
    - _cached_sequence is invalidated on every register_touch() call.
    """

    trace_id: str

    files: dict[str, FileNode] = field(default_factory=dict)
    event_file_index: dict[int, str] = field(default_factory=dict)

    imports: dict[str, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    symbols: dict[str, Symbol] = field(default_factory=dict)
    transitions: list[tuple[str, str]] = field(default_factory=list)
    reverse_imports: dict[str, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    neighbors: dict[str, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )

    # Internal memoization cache — not part of the public interface
    _cached_sequence: list[str] | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def add_import(self, source: str, target: str) -> None:
        """Record source → target import and the corresponding reverse edge.

        This is the ONLY correct way to populate import relationships.
        Writing to self.imports[src] directly bypasses reverse_imports and
        breaks SemanticContinuityAnalyzer and DependencyJumpAnalyzer.
        """
        self.imports[source].add(target)
        self.reverse_imports[target].add(source)

    def add_neighbor(self, source: str, target: str) -> None:
        """Record non-dependency semantic adjacency for locality scoring."""
        self.neighbors[source].add(target)

    def add_symbol(self, symbol: Symbol) -> None:
        """Index a symbol definition by its fully qualified and short names."""
        self.symbols[symbol.name] = symbol
        short_name = symbol.name.rsplit(".", maxsplit=1)[-1]
        self.symbols.setdefault(short_name, symbol)
        if symbol.file_path in self.files:
            self.files[symbol.file_path].symbol_names.append(symbol.name)

    def dependency_graph(self) -> dict[str, set[str]]:
        """Return an undirected view of import relationships for graph metrics."""
        graph: dict[str, set[str]] = {path: set() for path in self.files}
        for src, targets in self.imports.items():
            graph.setdefault(src, set()).update(targets)
            for dst in targets:
                graph.setdefault(dst, set()).add(src)
        return graph

    @staticmethod
    def shortest_distances(
        graph: dict[str, set[str]],
        source: str,
        max_hops: int | None = None,
    ) -> dict[str, int]:
        """Return dependency distances from one source, optionally capped."""
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

    def register_touch(self, seq: int, path: str) -> None:
        """Record that event at position *seq* touched file *path*.

        Args:
            seq:  Event sequence number (must be unique per path).
            path: Canonical file path string.

        Raises:
            ValueError: When *seq* is already registered to a different path
                        (sequence collision would corrupt metrics).
        """
        if seq in self.event_file_index:
            existing = self.event_file_index[seq]
            if existing != path:
                raise ValueError(
                    f"Conflicting paths for seq={seq}: {existing!r} vs {path!r}"
                )
            # Same seq + same path is idempotent — no-op
            return

        if path not in self.files:
            self.files[path] = FileNode(path=path)
        self.files[path].touch_count += 1
        self.event_file_index[seq] = path
        self._cached_sequence = None  # Invalidate cache on every new touch

    def touch_sequence(self) -> list[str]:
        """Return file paths in event-sequence order (memoized).

        The result is sorted by sequence key so gaps in sequence numbers
        (e.g., non-file events that were skipped) do not corrupt ordering.
        """
        if self._cached_sequence is None:
            self._cached_sequence = [
                self.event_file_index[k] for k in sorted(self.event_file_index)
            ]
        return self._cached_sequence
