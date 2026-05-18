"""Language adapter boundary for semantic extraction."""

from localitylens.semantic.languages.go import GoLanguageAdapter
from localitylens.semantic.languages.python import PythonLanguageAdapter

__all__ = ["GoLanguageAdapter", "PythonLanguageAdapter"]
