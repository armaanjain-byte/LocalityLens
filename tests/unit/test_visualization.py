"""Unit tests for report rendering visualization components."""

from localitylens.core.metrics import AnalysisReport, MetricResult, Severity
from localitylens.visualization.charts import MarkdownReportVisualizer


def test_markdown_report_visualizer_formatting():
    """Verify markdown output strings assemble into proper structured markdown elements."""
    visualizer = MarkdownReportVisualizer()
    report = AnalysisReport(trace_id="viz_test_trace", summary="Session execution flagged anomalies.")
    report.metrics.append(
        MetricResult(
            name="mock_metric",
            value=0.88762,
            severity=Severity.HIGH,
            details="Abnormal density signature caught."
        )
    )

    markdown_output = visualizer.render(report)

    # Validate high-level header structures exist cleanly
    assert "# LocalityLens Audit Report" in markdown_output
    assert "**Trace ID:** `viz_test_trace`" in markdown_output
    assert "🔴 `HIGH`" in markdown_output
    assert "mock_metric" in markdown_output
    assert "Abnormal density signature caught." in markdown_output
    assert "## Executive Summary Verdict" in markdown_output