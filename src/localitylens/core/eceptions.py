"""Domain exceptions for LocalityLens."""


class LocalityLensError(Exception):
    """Base class for all LocalityLens errors."""


class ParseError(LocalityLensError):
    """Raised when a trace file cannot be parsed."""


class ValidationError(LocalityLensError):
    """Raised when a data model fails validation."""


class AnalysisError(LocalityLensError):
    """Raised when an analysis engine encounters an unrecoverable error."""


class StorageError(LocalityLensError):
    """Raised for database or persistence failures."""


class UnsupportedFormatError(ParseError):
    """Raised when the input format is not supported by any parser."""