"""Semantic mapper: builds SemanticMap from a Trace."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace

_IGNORED_TARGETS = frozenset({"session", "unknown_file", "search_operation"})


class SemanticMapper:
    """
    Build lightweight semantic relationships from a Trace.

    Responsibilities:
    - Register every file touch so LocalityAnalyzer has a populated touch_sequence.
    - Reconstruct the transition graph (src → dst pairs).
    - Infer dependency adjacency: files in the same parent directory are
      considered semantically adjacent (lightweight heuristic; real AST
      import extraction can replace this later).
    - Build reverse dependency lookups via add_import() so both
      SemanticContinuityAnalyzer and DependencyJumpAnalyzer work correctly.
    """

    def build(self, trace: Trace) -> SemanticMap:
        smap = SemanticMap(trace_id=trace.trace_id)
        previous: str | None = None

        # ------------------------------------------------------------------
        # Pass 1: register touches and build transition graph
        # ------------------------------------------------------------------
        for event in trace.events:
            current = getattr(event, "target", None)
            if not current or current in _IGNORED_TARGETS:
                continue

            # Populate event_file_index so touch_sequence() works for LocalityAnalyzer
            smap.register_touch(event.sequence, current)

            # Transition graph
            if previous and previous != current:
                smap.transitions.append((previous, current))

            previous = current

        # ------------------------------------------------------------------
        # Pass 2: lightweight directory-based dependency inference
        #
        # Files inside the same parent directory are treated as semantically
        # adjacent. add_import() correctly populates BOTH imports AND
        # reverse_imports in one call, fixing SemanticContinuityAnalyzer
        # and DependencyJumpAnalyzer which both rely on reverse_imports.
        # ------------------------------------------------------------------
        parent_buckets: dict[str, list[str]] = defaultdict(list)

        unique_files = {
            event.target
            for event in trace.events
            if getattr(event, "target", None) and event.target not in _IGNORED_TARGETS
        }

        for file_path in unique_files:
            parent = str(Path(file_path).parent)
            parent_buckets[parent].append(file_path)

        for files in parent_buckets.values():
            for src in files:
                for dst in files:
                    if src != dst:
                        # Use the API — this populates BOTH imports and reverse_imports
                        smap.add_import(src, dst)

        return smap