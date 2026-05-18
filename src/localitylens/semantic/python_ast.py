"""Python AST extraction for repository semantic indexing."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from localitylens.semantic.symbols import Symbol, SymbolKind


@dataclass(frozen=True)
class PythonModuleSemantics:
    """Semantic facts extracted from one Python source file."""

    path: str
    module_name: str
    imports: set[str] = field(default_factory=set)
    symbols: list[Symbol] = field(default_factory=list)


def extract_python_semantics(file_path: Path, logical_path: str | None = None) -> PythonModuleSemantics:
    """Parse a Python file and return imports plus class/function/method symbols."""
    logical = logical_path or file_path.as_posix()
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    module_name = module_name_from_path(logical)

    return PythonModuleSemantics(
        path=logical,
        module_name=module_name,
        imports=extract_imports(tree, logical),
        symbols=extract_symbols(tree, logical, module_name),
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
