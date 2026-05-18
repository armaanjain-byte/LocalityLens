"""Python AST extraction for repository semantic indexing."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from localitylens.semantic.symbols import CallSite, Symbol, SymbolKind, SymbolReference


@dataclass(frozen=True)
class PythonModuleSemantics:
    """Semantic facts extracted from one Python source file."""

    path: str
    module_name: str
    imports: set[str] = field(default_factory=set)
    imported_symbols: dict[str, str] = field(default_factory=dict)
    symbols: list[Symbol] = field(default_factory=list)
    references: list[SymbolReference] = field(default_factory=list)
    call_edges: set[tuple[str, str]] = field(default_factory=set)
    call_sites: list[CallSite] = field(default_factory=list)


def extract_python_semantics(
    file_path: Path,
    logical_path: str | None = None,
) -> PythonModuleSemantics:
    """Parse a Python file and return imports plus class/function/method symbols."""
    logical = logical_path or file_path.as_posix()
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    module_name = module_name_from_path(logical)
    imported_symbols = extract_imported_symbols(tree)
    symbols = extract_symbols(tree, logical, module_name)
    local_symbols = {symbol.name.rsplit(".", 1)[-1]: symbol.name for symbol in symbols}
    call_sites = extract_call_sites(tree, logical, module_name, imported_symbols, local_symbols)

    return PythonModuleSemantics(
        path=logical,
        module_name=module_name,
        imports=extract_imports(tree, logical),
        imported_symbols=imported_symbols,
        symbols=symbols,
        references=extract_references(tree, logical, module_name, imported_symbols, local_symbols),
        call_edges={
            (site.caller, site.resolved_symbol or site.callee)
            for site in call_sites
            if site.caller
        },
        call_sites=call_sites,
    )


def module_name_from_path(path: str) -> str:
    """Convert a Python file path into an import-style module name."""
    parts = list(Path(path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def extract_imports(tree: ast.AST, source_path: str) -> set[str]:
    """Extract imported module candidates from an AST."""
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


def extract_imported_symbols(tree: ast.AST) -> dict[str, str]:
    """Map local import aliases to fully qualified imported names."""
    imports: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                imports[local_name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if alias.name == "*":
                    continue
                local_name = alias.asname or alias.name
                imports[local_name] = f"{module}.{alias.name}" if module else alias.name

    return imports


def extract_symbols(tree: ast.AST, file_path: str, module_name: str | None = None) -> list[Symbol]:
    """Extract top-level classes/functions and class methods with line numbers."""
    module = module_name or module_name_from_path(file_path)
    symbols: list[Symbol] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            class_name = f"{module}.{node.name}" if module else node.name
            symbols.append(
                Symbol(
                    name=class_name,
                    kind=SymbolKind.CLASS,
                    file_path=file_path,
                    line=node.lineno,
                )
            )
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(
                        Symbol(
                            name=f"{class_name}.{child.name}",
                            kind=SymbolKind.FUNCTION,
                            file_path=file_path,
                            line=child.lineno,
                        )
                    )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(
                Symbol(
                    name=f"{module}.{node.name}" if module else node.name,
                    kind=SymbolKind.FUNCTION,
                    file_path=file_path,
                    line=node.lineno,
                )
            )

    return symbols


def extract_references(
    tree: ast.AST,
    file_path: str,
    module_name: str | None = None,
    imported_symbols: dict[str, str] | None = None,
    local_symbols: dict[str, str] | None = None,
) -> list[SymbolReference]:
    """Extract name and attribute references with their enclosing scope."""
    module = module_name or module_name_from_path(file_path)
    imports = imported_symbols or {}
    locals_by_name = local_symbols or {}
    references: list[SymbolReference] = []

    for parent_scope, node in _scoped_walk(tree, module):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            references.append(
                SymbolReference(
                    name=node.id,
                    file_path=file_path,
                    line=node.lineno,
                    scope=parent_scope,
                    resolved_symbol=_resolve_symbol(node.id, imports, locals_by_name),
                )
            )
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            name = _attribute_name(node)
            references.append(
                SymbolReference(
                    name=name,
                    file_path=file_path,
                    line=node.lineno,
                    scope=parent_scope,
                    resolved_symbol=_resolve_symbol(name, imports, locals_by_name),
                )
            )

    return references


def extract_call_edges(tree: ast.AST, module_name: str | None = None) -> set[tuple[str, str]]:
    """Extract caller -> callee relationships visible from Python call sites."""
    module = module_name or ""
    edges: set[tuple[str, str]] = set()

    for scope, node in _scoped_walk(tree, module):
        if isinstance(node, ast.Call) and scope:
            callee = _call_name(node.func)
            if callee:
                edges.add((scope, callee))

    return edges


def extract_call_sites(
    tree: ast.AST,
    file_path: str,
    module_name: str | None = None,
    imported_symbols: dict[str, str] | None = None,
    local_symbols: dict[str, str] | None = None,
) -> list[CallSite]:
    """Extract call sites with local/import ownership resolution."""
    module = module_name or module_name_from_path(file_path)
    imports = imported_symbols or {}
    locals_by_name = local_symbols or {}
    sites: list[CallSite] = []

    for scope, node in _scoped_walk(tree, module):
        if isinstance(node, ast.Call) and scope:
            callee = _call_name(node.func)
            if callee:
                sites.append(
                    CallSite(
                        caller=scope,
                        callee=callee,
                        file_path=file_path,
                        line=node.lineno,
                        resolved_symbol=_resolve_symbol(callee, imports, locals_by_name),
                    )
                )

    return sites


def _resolve_symbol(
    name: str,
    imported_symbols: dict[str, str],
    local_symbols: dict[str, str],
) -> str | None:
    if name in local_symbols:
        return local_symbols[name]
    if name in imported_symbols:
        return imported_symbols[name]

    root, _, attr = name.partition(".")
    if root in imported_symbols:
        base = imported_symbols[root]
        return f"{base}.{attr}" if attr else base

    return None


def _scoped_walk(tree: ast.AST, module_name: str) -> list[tuple[str | None, ast.AST]]:
    scoped_nodes: list[tuple[str | None, ast.AST]] = []

    def visit(node: ast.AST, scope: str | None, class_scope: str | None = None) -> None:
        next_scope = scope
        next_class = class_scope
        if isinstance(node, ast.ClassDef):
            next_scope = f"{module_name}.{node.name}" if module_name else node.name
            next_class = next_scope
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if class_scope:
                next_scope = f"{class_scope}.{node.name}"
            else:
                next_scope = f"{module_name}.{node.name}" if module_name else node.name

        scoped_nodes.append((scope, node))
        for child in ast.iter_child_nodes(node):
            visit(child, next_scope, next_class)

    visit(tree, None)
    return scoped_nodes


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _attribute_name(node)
    return None


def _attribute_name(node: ast.Attribute) -> str:
    parts = [node.attr]
    current = node.value
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    parts.reverse()
    return ".".join(parts)
