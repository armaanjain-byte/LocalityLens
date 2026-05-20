"""Semantic map indexers with memoization caching optimization."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from localitylens.semantic.symbols import CallSite, Symbol, SymbolDefinition, SymbolReference


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
    symbol_definitions: dict[str, Symbol] = field(default_factory=dict)
    definitions_by_symbol: dict[str, SymbolDefinition] = field(default_factory=dict)
    symbol_references: dict[str, list[SymbolReference]] = field(
        default_factory=lambda: defaultdict(list)
    )
    references_by_symbol: dict[str, list[SymbolReference]] = field(
        default_factory=lambda: defaultdict(list)
    )
    call_graph: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    symbol_call_graph: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    calls_by_symbol: dict[str, list[CallSite]] = field(default_factory=lambda: defaultdict(list))
    owners_by_reference: dict[SymbolReference, str] = field(default_factory=dict)
    import_aliases: dict[str, dict[str, str]] = field(default_factory=dict)
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
        self.symbol_definitions[symbol.name] = symbol
        self.definitions_by_symbol[symbol.name] = SymbolDefinition(
            name=symbol.name,
            kind=symbol.kind,
            file_path=symbol.file_path,
            line=symbol.line,
            module=symbol.name.rsplit(".", 1)[0] if "." in symbol.name else "",
        )
        short_name = symbol.name.rsplit(".", maxsplit=1)[-1]
        self.symbols.setdefault(short_name, symbol)
        if symbol.file_path in self.files:
            self.files[symbol.file_path].symbol_names.append(symbol.name)

    def add_symbol_reference(self, reference: SymbolReference) -> None:
        """Record a symbol-like reference found in source."""
        self.symbol_references[reference.name].append(reference)
        owner = reference.resolved_symbol or self._resolve_reference_name(reference.name)
        if owner:
            self.references_by_symbol[owner].append(reference)
            self.owners_by_reference[reference] = owner

    def add_call(self, caller: str, callee: str) -> None:
        """Record a caller -> callee relationship."""
        self.call_graph[caller].add(callee)
        self.symbol_call_graph[caller].add(callee)

    def add_call_site(self, call_site: CallSite) -> None:
        """Record a call site and update the call graph by resolved target."""
        target = call_site.resolved_symbol or call_site.callee
        self.call_graph[call_site.caller].add(target)
        self.symbol_call_graph[call_site.caller].add(target)
        self.calls_by_symbol[call_site.caller].append(call_site)

    def add_import_aliases(self, file_path: str, aliases: dict[str, str]) -> None:
        """Record import alias ownership for a file."""
        self.import_aliases.setdefault(file_path, {}).update(aliases)

    def concepts_for_file(self, path: str) -> set[str]:
        """Return symbols and owned references active for a file."""
        concepts = set(self.files.get(path, FileNode(path)).symbol_names)
        for references in self.symbol_references.values():
            for reference in references:
                if reference.file_path != path:
                    continue
                owner = self.owners_by_reference.get(reference) or reference.resolved_symbol
                if owner:
                    concepts.add(owner)
        if not concepts and path in self.files:
            concepts.add(path)
        return concepts

    def module_for_symbol(self, symbol_name: str) -> str:
        """Return the module-like owner for a symbol or path fallback."""
        definition = self.definitions_by_symbol.get(symbol_name)
        if definition:
            return definition.module
        if "/" in symbol_name or "\\" in symbol_name:
            return symbol_name.rsplit(".", 1)[0].replace("/", ".").replace("\\", ".")
        return symbol_name.rsplit(".", 1)[0] if "." in symbol_name else symbol_name

    def concept_sequence(self) -> list[str]:
        """Project touched files into primary semantic concepts."""
        sequence: list[str] = []
        for path in self.touch_sequence():
            concepts = sorted(self.concepts_for_file(path))
            sequence.append(concepts[0] if concepts else path)
        return sequence

    def semantic_neighbors(self, path: str) -> set[str]:
        """Return files connected through imports, references, calls, or adjacency."""
        connected = set(self.imports.get(path, set()))
        connected.update(self.reverse_imports.get(path, set()))
        connected.update(self.neighbors.get(path, set()))

        for symbol in self.files.get(path, FileNode(path)).symbol_names:
            for callee in self.call_graph.get(symbol, set()):
                target = self.symbols.get(callee) or self.symbols.get(
                    callee.rsplit(".", 1)[-1]
                )
                if target and target.file_path != path:
                    connected.add(target.file_path)

        for references in self.symbol_references.values():
            for reference in references:
                if reference.file_path != path:
                    continue
                target = self.symbols.get(reference.name) or self.symbols.get(
                    reference.name.rsplit(".", 1)[-1]
                )
                if reference.resolved_symbol:
                    target = self.symbols.get(reference.resolved_symbol) or target
                if target and target.file_path != path:
                    connected.add(target.file_path)

        return connected

    def _resolve_reference_name(self, name: str) -> str | None:
        if name in self.symbol_definitions:
            return name
        short_name = name.rsplit(".", 1)[-1]
        symbol = self.symbols.get(short_name)
        return symbol.name if symbol else None

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
