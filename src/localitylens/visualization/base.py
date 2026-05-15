"""Base protocol and helpers for visualization backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from localitylens.core.metrics import AnalysisReport


@runtime_checkable
class VisualizerProtocol(Protocol):
    """Structural protocol every visualizer must satisfy."""

    def render(self, report: AnalysisReport) -> str:
        """Render *report* and return a string representation."""
        ...


class BaseVisualizer(ABC):
    """Abstract base for report visualizers."""

    @abstractmethod
    def render(self, report: AnalysisReport) -> str:
        """Render *report* and return a string representation.

        Args:
            report: The analysis report to visualize.

        Returns:
            String output suitable for stdout or file writing.
        """