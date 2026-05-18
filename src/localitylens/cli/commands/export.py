"""CLI command to export analysis reports."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

import typer
from rich.console import Console

from localitylens.storage.db import ReportStore
from localitylens.visualization.charts import MarkdownReportVisualizer

app = typer.Typer()
console = Console()


class ExportFormat(str, Enum):
    """Supported export formats."""
    JSON = "json"
    MARKDOWN = "md"


@app.command("report")
def export_report(
    trace_id: str = typer.Argument(..., help="Trace ID to export"),
    output: Path = typer.Option(..., "--output", "-o", help="Output file path"),
    fmt: ExportFormat = typer.Option(ExportFormat.JSON, "--format", "-f", help="Output format"),
    db_path: Path = typer.Option(Path("localitylens.db"), help="Path to SQLite database"),
) -> None:
    """Export a stored analysis report to a file."""
    try:
        # Guard: ensure the output parent directory exists
        output.parent.mkdir(parents=True, exist_ok=True)

        store = ReportStore(db_path)
        report = store.load(trace_id)

        if not report:
            console.print(f"[bold red]Error:[/bold red] No report found for trace '{trace_id}'")
            raise typer.Exit(code=1)

        if fmt is ExportFormat.MARKDOWN:
            content = MarkdownReportVisualizer().render(report)
            output.write_text(content, encoding="utf-8")
        else:
            data = {
                "trace_id": report.trace_id,
                "summary": report.summary,
                "anomalies": report.anomalies,
                "metrics": [
                    {
                        "name": m.name,
                        "value": m.value,
                        "severity": m.severity.value,
                        "details": m.details,
                        "extra": m.extra,
                    }
                    for m in report.metrics
                ],
            }
            output.write_text(json.dumps(data, indent=2), encoding="utf-8")

        console.print(f"[bold green]Success:[/bold green] Exported report to {output}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("list")
def list_reports(
    db_path: Path = typer.Option(Path("localitylens.db"), help="Path to SQLite database"),
) -> None:
    """List all trace IDs stored in the database."""
    try:
        store = ReportStore(db_path)
        ids = store.list_ids()

        if not ids:
            console.print("No reports found in database.")
            return

        console.print("[bold]Stored Trace IDs:[/bold]")
        for tid in ids:
            console.print(f" - {tid}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
