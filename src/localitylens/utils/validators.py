"""Input validation helpers used across the CLI and parsers."""

from pathlib import Path

from localitylens.core.exceptions import ParseError


def validate_file_exists(path: Path) -> Path:
    """Raise :class:`ParseError` when *path* does not exist.

    Args:
        path: Filesystem path to check.

    Returns:
        The same *path* if valid.

    Raises:
        ParseError: When the path does not point to an existing file.
    """
    if not path.is_file():
        raise ParseError(f"File not found: {path}")
    return path


def validate_nonempty_string(value: str, field: str = "value") -> str:
    """Raise :class:`ValueError` when *value* is empty or whitespace-only.

    Args:
        value: String to validate.
        field: Human-readable field name used in the error message.

    Returns:
        Stripped *value* if valid.

    Raises:
        ValueError: When *value* is blank.
    """
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field} must not be empty")
    return stripped


def validate_positive_int(value: int, field: str = "value") -> int:
    """Raise :class:`ValueError` when *value* is not a positive integer.

    Args:
        value: Integer to validate.
        field: Human-readable field name used in the error message.

    Returns:
        *value* if valid.

    Raises:
        ValueError: When *value* <= 0.
    """
    if value <= 0:
        raise ValueError(f"{field} must be a positive integer, got {value}")
    return value
