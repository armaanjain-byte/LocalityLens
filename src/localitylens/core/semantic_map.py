"""Semantic map indexers with memoization caching optimization."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class FileNode:
    """A source file referenced in a trace."""

    path: str
    touch_count: int = 0
    symbol_names: list[str] = field(default_factory=list)


@dataclass
class SemanticMap:
    

    trace_id: str

    files: dict[str, FileNode] = field(default_factory=dict)
    event_file_index: dict[int, str] = field(default_factory=dict)
    imports: dict[str, set[str]] = field(
    default_factory=lambda: defaultdict(set)
    )

    transitions: list[tuple[str, str]] = field(
    default_factory=list
    )

    reverse_imports: dict[str, set[str]] = field(
    default_factory=lambda: defaultdict(set)
    )

    _cached_sequence: list[str] | None = field(
        default=None,
        init=False,
        repr=False,
    )
    
     
    def add_import(self, source: str, target: str) -> None:
        self.imports[source].add(target)
        self.reverse_imports[target].add(source)

    def register_touch(self, seq: int, path: str) -> None:
        """Record file interactions with validation guards."""
        # M-3: Prevent sequence collisions from corrupting metrics
        if seq in self.event_file_index:
            existing = self.event_file_index[seq]
            if existing != path:
                raise ValueError(
                    f"Conflicting paths for seq={seq}: {existing!r} vs {path!r}"
                )
            return

        if path not in self.files:
            self.files[path] = FileNode(path=path)
        self.files[path].touch_count += 1
        self.event_file_index[seq] = path
        self._cached_sequence = None  # Invalidate the cache on alterations

    def touch_sequence(self) -> list[str]:
        """Return file paths in event order using a cached sequence."""
        # M-2: Memoized lookup eliminates redundant sort algorithms
        if self._cached_sequence is None:
            self._cached_sequence = [
                self.event_file_index[k] for k in sorted(self.event_file_index)
            ]
        return self._cached_sequence