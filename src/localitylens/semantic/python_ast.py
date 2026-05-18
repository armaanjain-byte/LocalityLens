"""Python AST extraction for repository semantic indexing."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from localitylens.semantic.symbols import Symbol, SymbolKind, SymbolReference


@dataclass(frozen=True)
class PythonModuleSemantics:
    """Semantic facts extracted from one Python source file."""

    path: str
    module_name: str
    imports: set[str] = field(default_factory=set)
    symbols: list[Symbol] = field(default_factory=list)
    references: list[SymbolReference] = field(default_factory=list)
    call_edges: set[tuple[str, str]] = field(default_factory=set)


def extract_python_semantics(
    file_path: Path,
    logical_path: str | None = None,
) -> PythonModuleSemantics:
    """Parse a Python file and return imports plus class/function/method symbols."""
    logical = logical_path or file_path.as_posix()
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    module_name = module_name_from_path(logical)

    return PythonModuleSemantics(
        path=logical,
        module_name=module_name,
        imports=extract_imports(tree, logical),
        symbols=extract_symbols(tree, logical, module_name),
        references=extract_references(tree, logical, module_name),
        call_edges=extract_call_edges(tree, module_name),
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
) -> list[SymbolReference]:
    """Extract name and attribute references with their enclosing scope."""
    module = module_name or module_name_from_path(file_path)
    references: list[SymbolReference] = []

    for parent_scope, node in _scoped_walk(tree, module):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            references.append(
                SymbolReference(
                    name=node.id,
                    file_path=file_path,
                    line=node.lineno,
                    scope=parent_scope,
                )
            )
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            references.append(
                SymbolReference(
                    name=_attribute_name(node),
                    file_path=file_path,
                    line=node.lineno,
                    scope=parent_scope,
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
