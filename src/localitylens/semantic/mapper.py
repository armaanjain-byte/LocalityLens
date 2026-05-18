"""Semantic mapper: builds SemanticMap from a Trace."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.semantic.python_ast import extract_python_semantics, module_name_from_path
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

    def build(self, trace: Trace) -> SemanticMap:
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

        unique_files = {
            event.target
            for event in trace.events
            if getattr(event, "target", None) and event.target not in _IGNORED_TARGETS
        }

        self._populate_ast_imports(smap, unique_files, trace.source)
        self._populate_directory_neighbors(smap, unique_files)

        return smap

    def _populate_ast_imports(
        self,
        smap: SemanticMap,
        unique_files: set[str],
        trace_source: str,
    ) -> None:
        module_index = self._module_index(unique_files)
        source_root = Path(trace_source).resolve().parent if trace_source else Path.cwd()

        for file_path in unique_files:
            if Path(file_path).suffix != ".py":
                continue

            resolved = self._resolve_file(file_path, source_root)
            if not resolved:
                continue

            try:
                semantics = extract_python_semantics(resolved, logical_path=file_path)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue

            for symbol in semantics.symbols:
                smap.add_symbol(symbol)

            for module_name in semantics.imports:
                target = module_index.get(module_name)
                if target and target != file_path:
                    smap.add_import(file_path, target)

    @staticmethod
    def _populate_directory_neighbors(smap: SemanticMap, unique_files: set[str]) -> None:
        parent_buckets: dict[str, list[str]] = defaultdict(list)
        for file_path in unique_files:
            parent_buckets[str(Path(file_path).parent)].append(file_path)

        for files in parent_buckets.values():
            for src in files:
                for dst in files:
                    if src != dst:
                        smap.add_neighbor(src, dst)

    @staticmethod
    def _module_index(files: set[str]) -> dict[str, str]:
        index: dict[str, str] = {}
        for file_path in files:
            path = Path(file_path)
            if path.suffix != ".py":
                continue

            module_name = module_name_from_path(file_path)
            if not module_name:
                continue

            SemanticMapper._put_module_index(index, module_name, file_path)
            SemanticMapper._put_module_index(index, module_name.rsplit(".", maxsplit=1)[-1], file_path)

        return index

    @staticmethod
    def _put_module_index(index: dict[str, str], module_name: str, file_path: str) -> None:
        existing = index.get(module_name)
        if existing is None or len(file_path) > len(existing):
            if existing is not None:
                log.debug(
                    "Module name collision %r: %r vs %r (using longer path)",
                    module_name,
                    existing,
                    file_path,
                )
            index[module_name] = file_path

    @staticmethod
    def _resolve_file(file_path: str, source_root: Path) -> Path | None:
        candidates = (Path(file_path), source_root / file_path, Path.cwd() / file_path)
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved.is_file():
                return resolved
        return None
