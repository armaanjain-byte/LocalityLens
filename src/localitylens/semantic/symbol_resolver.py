"""Cross-module symbol ownership resolution."""

from __future__ import annotations

from localitylens.core.semantic_map import SemanticMap


class SymbolResolver:
    """Resolve local names, imported aliases, and method references to symbols."""

    def __init__(self, smap: SemanticMap) -> None:
        self.smap = smap

    def resolve(
        self,
        name: str,
        *,
        file_path: str,
        scope: str | None = None,
    ) -> str | None:
        """Return the best-known fully qualified symbol for a reference."""
        if name in self.smap.definitions_by_symbol:
            return name

        local = self._resolve_local(name, scope)
        if local:
            return local

        imported = self._resolve_imported(name, file_path)
        if imported:
            return imported

        method = self._resolve_method(name, scope)
        if method:
            return method

        short_name = name.rsplit(".", 1)[-1]
        symbol = self.smap.symbols.get(short_name)
        return symbol.name if symbol else None

    def _resolve_local(self, name: str, scope: str | None) -> str | None:
        if not scope:
            return None
        module = scope.rsplit(".", 1)[0]
        candidate = f"{module}.{name}"
        if candidate in self.smap.definitions_by_symbol:
            return candidate
        return None

    def _resolve_imported(self, name: str, file_path: str) -> str | None:
        aliases = self.smap.import_aliases.get(file_path, {})
        if name in aliases:
            return self._canonical_symbol(aliases[name])

        root, _, attr = name.partition(".")
        if root in aliases:
            imported = aliases[root]
            candidate = f"{imported}.{attr}" if attr else imported
            return self._canonical_symbol(candidate)

        return None

    def _resolve_method(self, name: str, scope: str | None) -> str | None:
        if not scope:
            return None

        class_scope = self._class_scope(scope)
        if not class_scope:
            return None

        method_name = name.split(".", 1)[1] if name.startswith("self.") else name
        candidate = f"{class_scope}.{method_name}"
        if candidate in self.smap.definitions_by_symbol:
            return candidate

        # Minimal inherited-method support: search base-class-shaped suffixes.
        suffix = f".{method_name}"
        matches = [
            symbol
            for symbol in self.smap.definitions_by_symbol
            if symbol.endswith(suffix) and symbol != candidate
        ]
        return sorted(matches)[0] if matches else None

    def _canonical_symbol(self, name: str) -> str | None:
        if name in self.smap.definitions_by_symbol:
            return name
        symbol = self.smap.symbols.get(name) or self.smap.symbols.get(name.rsplit(".", 1)[-1])
        return symbol.name if symbol else name

    @staticmethod
    def _class_scope(scope: str) -> str | None:
        parts = scope.split(".")
        if len(parts) < 2:
            return None
        return ".".join(parts[:-1])
