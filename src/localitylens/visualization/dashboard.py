"""Human-readable HTML dashboard generator."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from localitylens.core.metrics import AnalysisReport, Severity
from localitylens.reporting.findings import FindingsGenerator
from localitylens.reporting.session_story import SessionStoryGenerator


SEVERITY_COLORS = {
    "OK": "#22c55e",
    "LOW": "#84cc16",
    "MEDIUM": "#facc15",
    "HIGH": "#fb923c",
    "CRITICAL": "#ef4444",
}


class DashboardVisualizer:
    """Generate readable LocalityLens HTML dashboard."""

    def render(
        self,
        report: AnalysisReport,
        output_path: str | Path = "dashboard.html",
    ) -> str:
        findings = FindingsGenerator().generate(report)

        session_story = SessionStoryGenerator().generate(report)

        # ------------------------------------------------------------------
        # Severity summary
        # ------------------------------------------------------------------
        severity_counter = Counter(
            finding["severity"]
            for finding in findings
        )

        severity_cards = ""

        for severity in [
            "CRITICAL",
            "HIGH",
            "MEDIUM",
            "LOW",
            "OK",
        ]:
            count = severity_counter.get(severity, 0)

            severity_cards += f"""
            <div class="severity-card">
                <div class="severity-label">{severity}</div>

                <div
                    class="severity-count"
                    style="color:{SEVERITY_COLORS[severity]}"
                >
                    {count}
                </div>
            </div>
            """

        # ------------------------------------------------------------------
        # Primary issue
        # ------------------------------------------------------------------
        primary_finding = findings[0] if findings else None

        primary_issue_html = ""

        if primary_finding:
            primary_issue_html = f"""
            <div class="primary-issue">
                <div class="primary-title">
                    PRIMARY ISSUE DETECTED
                </div>

                <div class="primary-heading">
                    {primary_finding['title']}
                </div>

                <div class="primary-description">
                    {primary_finding['description']}
                </div>
            </div>
            """

        # ------------------------------------------------------------------
        # Findings cards
        # ------------------------------------------------------------------
        findings_html = ""

        for finding in findings:
            color = SEVERITY_COLORS.get(
                finding["severity"],
                "#ef4444",
            )

            findings_html += f"""
            <div class="card">
                <div class="card-header">
                    <h3>{finding['title']}</h3>

                    <span
                        class="badge"
                        style="background:{color}"
                    >
                        {finding['severity']}
                    </span>
                </div>

                <p>{finding['description']}</p>

                <div class="details">
                    {finding['details']}
                </div>
            </div>
            """

        # ------------------------------------------------------------------
        # HTML
        # ------------------------------------------------------------------
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>LocalityLens Dashboard</title>

<style>
body {{
    background: #0b1020;
    color: white;
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 30px;
}}

h1 {{
    margin-top: 0;
    margin-bottom: 10px;
}}

.subtitle {{
    color: #94a3b8;
    margin-bottom: 30px;
}}

.section {{
    margin-top: 40px;
}}

.primary-issue {{
    background: linear-gradient(
        135deg,
        #3b0a0a,
        #1f1111
    );

    border-left: 8px solid #ef4444;

    padding: 24px;

    border-radius: 16px;

    margin-bottom: 40px;
}}

.primary-title {{
    color: #fca5a5;

    font-size: 13px;

    letter-spacing: 0.08em;

    text-transform: uppercase;

    margin-bottom: 10px;
}}

.primary-heading {{
    font-size: 34px;

    font-weight: bold;

    margin-bottom: 14px;
}}

.primary-description {{
    color: #f3f4f6;

    line-height: 1.7;

    font-size: 17px;
}}

.severity-grid {{
    display: grid;

    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));

    gap: 18px;

    margin-top: 20px;
}}

.severity-card {{
    background: #111827;

    padding: 20px;

    border-radius: 14px;

    text-align: center;
}}

.severity-label {{
    color: #94a3b8;

    margin-bottom: 12px;

    font-size: 13px;

    letter-spacing: 0.06em;
}}

.severity-count {{
    font-size: 34px;

    font-weight: bold;
}}

.story {{
    background: #111827;

    padding: 24px;

    border-radius: 16px;

    line-height: 1.8;

    color: #e5e7eb;
}}

.card {{
    background: #111827;

    padding: 24px;

    border-radius: 16px;

    margin-bottom: 20px;

    border-left: 6px solid #ef4444;
}}

.card-header {{
    display: flex;

    justify-content: space-between;

    align-items: center;

    margin-bottom: 14px;
}}

.badge {{
    padding: 6px 12px;

    border-radius: 999px;

    color: white;

    font-size: 12px;

    font-weight: bold;
}}

.details {{
    margin-top: 16px;

    color: #cbd5e1;

    line-height: 1.7;
}}
</style>
</head>

<body>

<h1>LocalityLens Workflow Analysis</h1>

<div class="subtitle">
AST-assisted observability for coding-agent workflows
</div>

{primary_issue_html}

<div class="section">
    <h2>Severity Summary</h2>

    <div class="severity-grid">
        {severity_cards}
    </div>
</div>

<div class="section">
    <h2>Session Story</h2>

    <div class="story">
        {session_story}
    </div>
</div>

<div class="section">
    <h2>Key Findings</h2>

    {findings_html}
</div>

</body>
</html>
"""

        output = Path(output_path)

        output.write_text(html, encoding="utf-8")

        return str(output)