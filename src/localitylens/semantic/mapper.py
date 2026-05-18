"""Semantic mapper: builds SemanticMap from a Trace."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace

_IGNORED_TARGETS = frozenset({"session", "unknown_file", "search_operation"})


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

            smap.register_touch(event.sequence, current)

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
                tree = ast.parse(resolved.read_text(encoding="utf-8"), filename=str(resolved))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue

            smap.files[file_path].symbol_names = self._symbols(tree)

            for module_name in self._imported_modules(tree, file_path):
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

            parts = list(path.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            if not parts:
                continue

            module_name = ".".join(parts)
            index[module_name] = file_path
            index[parts[-1]] = file_path

        return index

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

    @staticmethod
    def _symbols(tree: ast.AST) -> list[str]:
        symbols: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(node.name)
        return symbols

    @staticmethod
    def _imported_modules(tree: ast.AST, source_path: str) -> set[str]:
        modules: set[str] = set()
        source_module_parts = list(Path(source_path).with_suffix("").parts)
        if source_module_parts and source_module_parts[-1] == "__init__":
            source_module_parts = source_module_parts[:-1]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    package = source_module_parts[:-node.level]
                    base_parts = base.split(".") if base else []
                    module = ".".join([*package, *base_parts])
                else:
                    module = base

                if module:
                    modules.add(module)
                for alias in node.names:
                    if alias.name != "*" and module:
                        modules.add(f"{module}.{alias.name}")

        return modules
