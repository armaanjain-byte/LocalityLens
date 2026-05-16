
from collections import defaultdict
from pathlib import Path

from localitylens.core.semantic_map import SemanticMap


class SemanticMapper:
    """
    Build lightweight semantic relationships from traces.

    Current responsibilities:
    - build transition graph
    - infer dependency adjacency
    - construct reverse dependency lookups
    - prepare semantic structures for analyzers

    This is intentionally lightweight right now.
    AST-level symbol extraction can be layered later.
    """

    def build(self, trace):
        smap = SemanticMap(trace_id=trace.trace_id)

        # Dynamic fields added during construction
        smap.transitions = []
        smap.reverse_imports = defaultdict(set)

        previous = None

        # -----------------------------
        # Transition reconstruction
        # -----------------------------
        for event in trace.events:
            current = getattr(event, "target", None)

            if not current:
                continue

            if current in (
                "session",
                "unknown_file",
                "search_operation",
            ):
                continue

            # Transition graph
            if previous and previous != current:
                smap.transitions.append((previous, current))

            previous = current

        # -----------------------------
        # Lightweight dependency inference
        # -----------------------------
        #
        # Current heuristic:
        # files inside same parent directory are
        # considered semantically adjacent.
        #
        # This is intentionally simple for now.
        # Real AST import extraction can replace it later.
        # -----------------------------

        parent_buckets = defaultdict(list)

        unique_files = {
            event.target
            for event in trace.events
            if getattr(event, "target", None)
            and event.target not in (
                "session",
                "unknown_file",
                "search_operation",
            )
        }

        for file_path in unique_files:
            parent = str(Path(file_path).parent)
            parent_buckets[parent].append(file_path)

        for files in parent_buckets.values():
            for src in files:
                smap.imports.setdefault(src, set())

                for dst in files:
                    if src != dst:
                        smap.imports[src].add(dst)

        # -----------------------------
        # Reverse dependency graph
        # -----------------------------

        for src, targets in smap.imports.items():
            for dst in targets:
                smap.reverse_imports[dst].add(src)

        return smap


#\