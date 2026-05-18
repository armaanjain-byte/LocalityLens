"""Unit tests for report rendering visualization components."""

from __future__ import annotations

from localitylens.core.metrics import AnalysisReport, MetricResult, Severity
from localitylens.visualization.charts import MarkdownReportVisualizer, TextReportVisualizer


class TestMarkdownReportVisualizer:
    def _make_report(self) -> AnalysisReport:
        report = AnalysisReport(
            trace_id="viz_test_trace",
            summary="Session execution flagged anomalies.",
        )
        report.metrics.append(
            MetricResult(
                name="mock_metric",
                value=0.88762,
                severity=Severity.HIGH,
                details="Abnormal density signature caught.",
            )
        )
        return report

    def test_header_structure(self):
        visualizer = MarkdownReportVisualizer()
        output = visualizer.render(self._make_report())
        assert "# LocalityLens Audit Report" in output

    def test_trace_id_present(self):
        visualizer = MarkdownReportVisualizer()
        output = visualizer.render(self._make_report())
        assert "**Trace ID:** `viz_test_trace`" in output

    def test_severity_badge_high(self):
        """HIGH severity must render an ASCII-safe badge."""
        visualizer = MarkdownReportVisualizer()
        output = visualizer.render(self._make_report())
        assert "`HIGH`" in output

    def test_metric_name_present(self):
        visualizer = MarkdownReportVisualizer()
        output = visualizer.render(self._make_report())
        assert "mock_metric" in output

    def test_metric_details_present(self):
        visualizer = MarkdownReportVisualizer()
        output = visualizer.render(self._make_report())
        assert "Abnormal density signature caught." in output

    def test_summary_section_present(self):
        visualizer = MarkdownReportVisualizer()
        output = visualizer.render(self._make_report())
        assert "## Executive Summary Verdict" in output
        assert "Session execution flagged anomalies." in output

    def test_no_summary_omits_section(self):
        visualizer = MarkdownReportVisualizer()
        report = AnalysisReport(trace_id="t")
        output = visualizer.render(report)
        assert "## Executive Summary Verdict" not in output

    def test_all_severity_badges_render(self):
        """Every Severity level must produce a non-empty badge in Markdown output."""
        visualizer = MarkdownReportVisualizer()
        for sev in Severity:
            report = AnalysisReport(trace_id="t")
            report.metrics.append(
                MetricResult(name="x", value=0.0, severity=sev, details="test")
            )
            output = visualizer.render(report)
            assert f"`{sev.value.upper()}`" in output

    def test_metric_value_formatted(self):
        """Metric value must appear formatted to 4 decimal places."""
        visualizer = MarkdownReportVisualizer()
        output = visualizer.render(self._make_report())
        assert "0.8876" in output


class TestTextReportVisualizer:
    def test_trace_id_in_header(self):
        visualizer = TextReportVisualizer()
        report = AnalysisReport(trace_id="my_trace")
        output = visualizer.render(report)
        assert "my_trace" in output

    def test_overall_severity_line(self):
        visualizer = TextReportVisualizer()
        report = AnalysisReport(trace_id="t")
        report.metrics.append(MetricResult(name="m", value=0.5, severity=Severity.HIGH))
        output = visualizer.render(report)
        assert "Overall Severity" in output
        assert "HIGH" in output

    def test_summary_present_when_set(self):
        visualizer = TextReportVisualizer()
        report = AnalysisReport(trace_id="t", summary="All good.")
        output = visualizer.render(report)
        assert "All good." in output

    def test_empty_report_no_crash(self):
        visualizer = TextReportVisualizer()
        report = AnalysisReport(trace_id="empty")
        output = visualizer.render(report)
        assert "LocalityLens Report" in output
