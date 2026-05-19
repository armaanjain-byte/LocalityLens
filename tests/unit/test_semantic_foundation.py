"""Focused tests for semantic foundation helper modules."""

from __future__ import annotations

import ast

import pytest

from localitylens.analysis.thrashing_patterns import oscillation_pairs, repeated_items
from localitylens.semantic.context_window import ContextWindowSimulator
from localitylens.semantic.languages.go import GoLanguageAdapter
from localitylens.semantic.languages.python import PythonLanguageAdapter
from localitylens.semantic.languages.rust import RustLanguageAdapter
from localitylens.semantic.languages.typescript import TypeScriptLanguageAdapter
from localitylens.semantic.python_ast import (
    extract_call_sites,
    extract_imported_symbols,
    extract_references,
)
from localitylens.semantic.repository_indexer import RepositoryIndexer
from localitylens.semantic.session_state import SessionState
from localitylens.semantic.symbol_resolver import SymbolResolver
from localitylens.utils.validators import (
    validate_file_exists,
    validate_nonempty_string,
    validate_positive_int,
)


def test_python_ast_resolves_import_alias_call_sites():
    tree = ast.parse("from auth import login as signin\n\ndef run():\n    return signin()\n")
    imports = extract_imported_symbols(tree)
    calls = extract_call_sites(tree, "main.py", "main", imports, {})
    references = extract_references(tree, "main.py", "main", imports, {})

    assert imports == {"signin": "auth.login"}
    assert calls[0].resolved_symbol == "auth.login"
    assert references[-1].resolved_symbol == "auth.login"


def test_python_ast_resolves_module_alias_attribute_call():
    tree = ast.parse("import auth.service as svc\n\ndef run():\n    return svc.login()\n")
    imports = extract_imported_symbols(tree)
    calls = extract_call_sites(tree, "main.py", "main", imports, {})

    assert imports == {"svc": "auth.service"}
    assert calls[0].resolved_symbol == "auth.service.login"


def test_repository_indexer_handles_missing_and_broken_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "broken.py").write_text("def nope(:\n", encoding="utf-8")

    indexer = RepositoryIndexer()
    smap = indexer.index_repository(repo)

    assert "broken.py" in smap.files
    assert indexer.resolve_file("missing.py", repo) is None


def test_symbol_resolver_resolves_imports_locals_and_methods(tmp_path):
    repo = tmp_path / "repo"
    package = repo / "pkg"
    package.mkdir(parents=True)
    (package / "auth.py").write_text("def login():\n    return True\n", encoding="utf-8")
    (package / "main.py").write_text(
        "from pkg.auth import login as signin\n\n"
        "def local():\n    return True\n\n"
        "class Handler:\n"
        "    def handle(self):\n"
        "        return self.local_method()\n"
        "    def local_method(self):\n"
        "        return signin()\n",
        encoding="utf-8",
    )
    smap = RepositoryIndexer().index_repository(repo)
    resolver = SymbolResolver(smap)

    assert resolver.resolve("signin", file_path="pkg/main.py") == "pkg.auth.login"
    assert resolver.resolve("local", file_path="pkg/main.py", scope="pkg.main.runner") == "pkg.main.local"
    assert (
        resolver.resolve(
            "self.local_method",
            file_path="pkg/main.py",
            scope="pkg.main.Handler.handle",
        )
        == "pkg.main.Handler.local_method"
    )


def test_language_adapters_report_supported_extensions(tmp_path):
    py_file = tmp_path / "a.py"
    py_file.write_text("def f():\n    return 1\n", encoding="utf-8")

    assert PythonLanguageAdapter().can_parse(py_file)
    assert PythonLanguageAdapter().parse(py_file, "a.py").module_name == "a"
    assert TypeScriptLanguageAdapter().can_parse(tmp_path / "a.tsx")
    assert RustLanguageAdapter().can_parse(tmp_path / "lib.rs")
    assert GoLanguageAdapter().can_parse(tmp_path / "main.go")


def test_context_window_rejects_invalid_capacity():
    with pytest.raises(ValueError, match="capacity"):
        ContextWindowSimulator(capacity=0)


def test_thrashing_pattern_helpers():
    assert oscillation_pairs(["a", "b", "a", "b"])[("a", "b")] == 1
    assert repeated_items(["a", "b", "a"], window=2) == 1
    with pytest.raises(ValueError, match="width"):
        oscillation_pairs(["a"], width=3)


def test_session_state_and_validators(tmp_path):
    file_path = tmp_path / "trace.json"
    file_path.write_text("[]", encoding="utf-8")
    state = SessionState()

    state.set_current_file("src/a.py")

    assert state.get_current_file() == "src/a.py"
    assert validate_file_exists(file_path) == file_path
    assert validate_nonempty_string("  hello ") == "hello"
    assert validate_positive_int(1) == 1

    with pytest.raises(ValueError):
        validate_nonempty_string(" ")
    with pytest.raises(ValueError):
        validate_positive_int(0)
