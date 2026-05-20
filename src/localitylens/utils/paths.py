from pathlib import Path


def normalize_path(path: str) -> str:
    """
    Normalize file paths into stable graph-safe identifiers.
    """

    if not path:
        return "unknown"

    path = path.strip().replace("\\\\", "/")

    # Remove URL fragments
    if "github.com" in path:
        path = path.split("/")[-1]

    # Remove duplicate slashes
    while "//" in path:
        path = path.replace("//", "/")

    # Normalize relative markers
    path = path.replace("./", "")

    return Path(path).as_posix().lower()