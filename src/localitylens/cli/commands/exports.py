"""CLI command to export analysis reports."""

import json
from pathlib import Path

import typer
from rich.console import Console

from localitylens.storage.db import ReportStore
from localitylens.utils.validators import validate_file_exists

app = typer.Typer()
console = Console()


@app.command("report")
def export_report(
    trace_id: str = typer.Argument(..., help="Trace ID to export"),
    output: Path = typer.Option(..., "--output", "-o", help="Output JSON file path"),
    db_path: Path = typer.Option(Path("localitylens.db"), help="Path to SQLite database"),
) -> None:
    """Export a stored analysis report to JSON."""
    try:
        store = ReportStore(db_path)
        report = store.load(trace_id)

        if not report:
            console.print(f"[bold red]Error:[/bold red] No report found for trace '{trace_id}'")
            raise typer.Exit(code=1)

        # Convert report dataclass to serialisable dict
        data = {
            "trace_id": report.trace_id,
            "summary": report.summary,
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

        output.write_text(json.dumps(data, indent=2))
        console.print(f"[bold green]Success:[/bold green] Exported report to {output}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("list")
def list_reports(
    db_path: Path = typer.Option(Path("localitylens.db"), help="Path to SQLite database"),
) -> None:
    """List all trace IDs currently stored in the database."""
    try:
        store = ReportStore(db_path)
        ids = store.list_ids()

        if not ids:
            console.print("No reports found in database.")
            return

        console.print("[bold]Stored Trace IDs:[/bold]")
        for trace_id in ids:
            console.print(f" - {trace_id}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)