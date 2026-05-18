"""Semantic mapper: builds SemanticMap from a Trace."""

from __future__ import annotations

from pathlib import Path

from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.semantic.repository_indexer import RepositoryIndexer
from localitylens.utils.logger import get_logger

_IGNORED_TARGETS = frozenset({"session", "unknown_file", "search_operation"})
log = get_logger(__name__)


class SemanticMapper:
    """
    Build semantic relationships from a Trace.

    Responsibilities:
    - Register every file touch so LocalityAnalyzer has a populated touch_sequence.
    - Reconstruct the transition graph from consecutive distinct file targets.
    - Extract Python import relationships with the stdlib AST parser.
    - Record same-directory neighbours separately for locality heuristics.
    - Build reverse dependency lookups via add_import().
    """

    def build(self, trace: Trace, repo_path: Path | None = None) -> SemanticMap:
        source_root = repo_path or (Path(trace.source).resolve().parent if trace.source else Path.cwd())
        indexer = RepositoryIndexer()

        repository_files = indexer.crawl(source_root) if repo_path else set()
        smap = SemanticMap(trace_id=trace.trace_id)

        previous: str | None = None

        for event in trace.events:
            current = getattr(event, "target", None)
            if not current or current in _IGNORED_TARGETS:
                continue

            try:
                smap.register_touch(event.sequence, current)
            except ValueError as exc:
                log.warning("Skipping duplicate sequence %d: %s", event.sequence, exc)
                continue

            if previous and previous != current:
                smap.transitions.append((previous, current))

            previous = current

        unique_files = repository_files | {
            event.target
            for event in trace.events
            if getattr(event, "target", None) and event.target not in _IGNORED_TARGETS
        }

        indexer.index_paths(unique_files, source_root, smap)
        self._populate_directory_neighbors(smap, unique_files)

        return smap

    @staticmethod
    def _populate_directory_neighbors(smap: SemanticMap, unique_files: set[str]) -> None:
        from collections import defaultdict

        parent_buckets: dict[str, list[str]] = defaultdict(list)
        for file_path in unique_files:
            parent_buckets[str(Path(file_path).parent)].append(file_path)

        for files in parent_buckets.values():
            for src in files:
                for dst in files:
                    if src != dst:
                        smap.add_neighbor(src, dst)
