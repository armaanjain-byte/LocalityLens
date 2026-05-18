"""Text-based chart renderers for terminal output."""

from __future__ import annotations

from localitylens.core.metrics import AnalysisReport, MetricResult, Severity
from localitylens.visualization.base import BaseVisualizer

# ANSI colour codes degrade gracefully on non-colour terminals.
_COLOUR: dict[Severity, str] = {
    Severity.OK: "\033[32m",
    Severity.LOW: "\033[36m",
    Severity.MEDIUM: "\033[33m",
    Severity.HIGH: "\033[31m",
    Severity.CRITICAL: "\033[35m",
}
_RESET = "\033[0m"

# Keep labels ASCII-safe because reports may be printed from Windows CP-1252 terminals.
_SEVERITY_BADGE: dict[Severity, str] = {
    Severity.OK: "`OK`",
    Severity.LOW: "`LOW`",
    Severity.MEDIUM: "`MEDIUM`",
    Severity.HIGH: "`HIGH`",
    Severity.CRITICAL: "`CRITICAL`",
}


def _colour(severity: Severity, text: str) -> str:
    return f"{_COLOUR[severity]}{text}{_RESET}"


def _ascii_safe(text: str) -> str:
    """Return text that can be printed by legacy Windows console encodings."""
    return (
        text.replace("≥", ">=")
        .replace("≤", "<=")
        .encode("ascii", errors="replace")
        .decode("ascii")
    )


class TextReportVisualizer(BaseVisualizer):
    """Render an AnalysisReport as a human-readable plain-text table."""

    def render(self, report: AnalysisReport) -> str:
        rule = "-" * 60
        lines: list[str] = [
            rule,
            f"  LocalityLens Report - trace: {_ascii_safe(report.trace_id)}",
            rule,
        ]

        for m in report.metrics:
            lines.append(self._format_metric(m))

        worst = report.worst_severity()
        lines += [
            rule,
            f"  Overall Severity: {_colour(worst, worst.value.upper())}",
            rule,
        ]
        if report.summary:
            lines.append(f"  {_ascii_safe(report.summary)}")

        return "\n".join(lines)

    @staticmethod
    def _format_metric(m: MetricResult) -> str:
        badge = _colour(m.severity, f"[{m.severity.value.upper():8}]")
        return (
            f"  {badge} "
            f"{m.name:<26} "
            f"{m.value:>10.4f}  "
            f"{_ascii_safe(m.details)}"
        )


class MarkdownReportVisualizer(BaseVisualizer):
    """Render an AnalysisReport as a structured Markdown document."""

    def render(self, report: AnalysisReport) -> str:
        worst = report.worst_severity()

        lines: list[str] = [
            "# LocalityLens Audit Report",
            "",
            f"**Trace ID:** `{report.trace_id}`  ",
            f"**Global Verdict:** `{worst.value.upper()}`",
            "",
            "## Summary Analysis Metrics",
            "",
            "| Status | Metric Name | Core Value | Diagnostic Analysis Details |",
            "| :--- | :--- | :---: | :--- |",
        ]

        for m in report.metrics:
            badge = _SEVERITY_BADGE[m.severity]
            lines.append(
                f"| {badge} "
                f"| **{m.name}** "
                f"| `{m.value:.4f}` "
                f"| {m.details} |"
            )

        if report.summary:
            lines.extend(
                [
                    "",
                    "## Executive Summary Verdict",
                    f"> {report.summary}",
                ]
            )

        return "\n".join(lines)
