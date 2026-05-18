"""Text-based chart renderers for terminal output."""

from __future__ import annotations

from localitylens.core.metrics import AnalysisReport, MetricResult, Severity
from localitylens.visualization.base import BaseVisualizer

# ANSI colour codes (degrade gracefully on non-colour terminals).
_COLOUR: dict[Severity, str] = {
    Severity.OK: "\033[32m",       # green
    Severity.LOW: "\033[36m",      # cyan
    Severity.MEDIUM: "\033[33m",   # yellow
    Severity.HIGH: "\033[31m",     # red
    Severity.CRITICAL: "\033[35m", # magenta
}
_RESET = "\033[0m"

# Severity badge labels used in Markdown output
_SEVERITY_BADGE: dict[Severity, str] = {
    Severity.OK: "✅ `OK`",
    Severity.LOW: "🟡 `LOW`",
    Severity.MEDIUM: "🟠 `MEDIUM`",
    Severity.HIGH: "🔴 `HIGH`",
    Severity.CRITICAL: "🚨 `CRITICAL`",
}


def _colour(severity: Severity, text: str) -> str:
    return f"{_COLOUR[severity]}{text}{_RESET}"


class TextReportVisualizer(BaseVisualizer):
    """Render an AnalysisReport as a human-readable plain-text table for terminal display."""

    def render(self, report: AnalysisReport) -> str:
        lines: list[str] = [
            f"{'─' * 60}",
            f"  LocalityLens Report — trace: {report.trace_id}",
            f"{'─' * 60}",
        ]

        for m in report.metrics:
            lines.append(self._format_metric(m))

        worst = report.worst_severity()
        lines += [
            f"{'─' * 60}",
            f"  Overall Severity: {_colour(worst, worst.value.upper())}",
            f"{'─' * 60}",
        ]
        if report.summary:
            lines.append(f"  {report.summary}")

        return "\n".join(lines)

    @staticmethod
    def _format_metric(m: MetricResult) -> str:
        badge = _colour(m.severity, f"[{m.severity.value.upper():8}]")
        return (
            f"  {badge} "
            f"{m.name:<26} "
            f"{m.value:>10.4f}  "
            f"{m.details}"
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
            lines.extend([
                "",
                "## Executive Summary Verdict",
                f"> {report.summary}",
            ])

        return "\n".join(lines)