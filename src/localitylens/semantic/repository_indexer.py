"""Repository-first semantic indexing."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from localitylens.core.semantic_map import FileNode, SemanticMap
from localitylens.semantic.python_ast import (
    PythonModuleSemantics,
    extract_python_semantics,
    module_name_from_path,
)
from localitylens.utils.logger import get_logger

log = get_logger(__name__)

SOURCE_EXTENSIONS = frozenset({".py", ".ts", ".tsx", ".js", ".rs", ".go"})
IGNORED_DIRS = frozenset({".git", ".venv", "__pycache__", "node_modules", ".semantic_cache"})
   
class RepositoryIndexer:
    """Build a semantic graph before trace projection."""
    
    SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".go",
    ".rs",
    }
    def __init__(self) -> None:
        self.supported_extensions = self.SUPPORTED_EXTENSIONS
 

    def index_repository(self, repo_path: Path, trace_id: str = "repository") -> SemanticMap:
        """Crawl and index a repository into a SemanticMap."""
        smap = SemanticMap(trace_id=trace_id)
        files = self.crawl(repo_path)
        self.index_paths(files, repo_path, smap)
        return smap

    def index_paths(self, files: set[str], source_root: Path, smap: SemanticMap) -> None:
        """Index a known logical path set relative to a source root."""
        for file_path in files:
            smap.files.setdefault(file_path, FileNode(path=file_path))

        module_index = self._module_index(files)
        python_files = [path for path in files if Path(path).suffix == ".py"]

        with ThreadPoolExecutor() as executor:
            results = executor.map(
                lambda logical: self._parse_python(logical, source_root),
                python_files,
            )

        for semantics in results:
            if semantics is None:
                continue

            for symbol in semantics.symbols:
                smap.add_symbol(symbol)
            smap.add_import_aliases(semantics.path, semantics.imported_symbols)
            for reference in semantics.references:
                smap.add_symbol_reference(reference)
            for call_site in semantics.call_sites:
                smap.add_call_site(call_site)

            for module_name in semantics.imports:
                target = module_index.get(module_name)
                if target and target != semantics.path:
                    smap.add_import(semantics.path, target)

    def crawl(self, repo_path: Path) -> list[Path]:
        """Crawl repository and collect source files."""

        repo_path = Path(repo_path)

        if not repo_path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

        if not repo_path.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {repo_path}")

        discovered_files: list[Path] = []

        for ext in self.supported_extensions:
            discovered_files.extend(repo_path.rglob(f"*{ext}"))

        return discovered_files

    @staticmethod
    def _parse_python(logical_path: str, source_root: Path) -> PythonModuleSemantics | None:
        resolved = RepositoryIndexer.resolve_file(logical_path, source_root)
        if not resolved:
            return None
        try:
            return extract_python_semantics(resolved, logical_path=logical_path)
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            log.debug("Skipping %s during semantic indexing: %s", logical_path, exc)
            return None

    @staticmethod
    def resolve_file(file_path: str, source_root: Path) -> Path | None:
        """Resolve a logical file path against likely roots."""
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
    def _module_index(files: set[str]) -> dict[str, str]:
        index: dict[str, str] = {}
        for file_path in files:
            if Path(file_path).suffix != ".py":
                continue

            module_name = module_name_from_path(file_path)
            if not module_name:
                continue

            RepositoryIndexer._put_module_index(index, module_name, file_path)
            RepositoryIndexer._put_module_index(
                index,
                module_name.rsplit(".", maxsplit=1)[-1],
                file_path,
            )

        return index

    @staticmethod
    def _put_module_index(index: dict[str, str], module_name: str, file_path: str) -> None:
        existing = index.get(module_name)
        if existing is None or len(file_path) > len(existing):
            index[module_name] = file_path
