"""Semantic map: links events to code symbols and files."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FileNode:
    """A source file referenced in a trace.

    Attributes:
        path: Absolute or repo-relative file path.
        touch_count: Number of events that touched this file.
        symbol_names: Symbols defined or referenced in this file.
    """

    path: str
    touch_count: int = 0
    symbol_names: list[str] = field(default_factory=list)


@dataclass
class SemanticMap:
    """Mapping from trace events to code entities.

    Attributes:
        trace_id: Trace this map was built from.
        files: All :class:`FileNode` objects keyed by path.
        event_file_index: Maps event sequence number to file path.
    """

    trace_id: str
    files: dict[str, FileNode] = field(default_factory=dict)
    event_file_index: dict[int, str] = field(default_factory=dict)

    def register_touch(self, seq: int, path: str) -> None:
        """Record that event *seq* touched *path*.

        Args:
            seq: Event sequence number.
            path: File path that was accessed.
        """
        if path not in self.files:
            self.files[path] = FileNode(path=path)
        self.files[path].touch_count += 1
        self.event_file_index[seq] = path

    def touch_sequence(self) -> list[str]:
        """Return file paths in event order.

        Returns:
            Ordered list of file paths, one per indexed event.
        """
        return [self.event_file_index[k] for k in sorted(self.event_file_index)]