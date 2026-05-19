"""CLI command to analyze a trace file."""

from __future__ import annotations

from pathlib import Path
from localitylens.visualization.replay_viewer import ReplayViewer
from localitylens.visualization.dashboard import DashboardVisualizer

import typer
from rich.console import Console

from localitylens.core.exceptions import LocalityLensError, UnsupportedFormatError
from localitylens.pipeline import (
    ANALYZER_REGISTRY,
    PARSERS,
    analyze_trace,
    build_semantic_map,
)
from localitylens.storage.db import ReportStore
from localitylens.utils.logger import get_logger
from localitylens.utils.validators import validate_file_exists
from localitylens.visualization.charts import TextReportVisualizer
from localitylens.visualization.replay_export import ReplayExporter
from localitylens.visualization.transition_graph import TransitionGraphVisualizer

app = typer.Typer()
log = get_logger(__name__)
console = Console()

ANALYZERS = ANALYZER_REGISTRY


@app.command("file")
def analyze_file(
    trace_path: Path = typer.Argument(..., help="Path to the agent trace file"),
    db_path: Path = typer.Option(Path("localitylens.db"), help="Path to SQLite database"),
    repo_path: Path | None = typer.Option(None, help="Repository root for semantic indexing"),
    output_dir: Path = typer.Option(Path("."), help="Directory for generated replay/graph files"),
    no_graph: bool = typer.Option(False, "--no-graph", help="Skip transition graph export"),
    no_replay: bool = typer.Option(False, "--no-replay", help="Skip replay frame export"),
) -> None:
    """Analyze a single trace file and display the report."""
    try:
        validate_file_exists(trace_path)

        parser = next((p for p in PARSERS if p.can_parse(trace_path)), None)
        if not parser:
            raise UnsupportedFormatError(f"No parser found for file: {trace_path.name}")

        console.print(f"[bold blue]Parsing[/bold blue] {trace_path.name} using {parser.format.value}...")
        trace = parser.parse(trace_path)
        smap = build_semantic_map(trace, repo_path=repo_path)
        report = analyze_trace(trace, smap)

        ReportStore(db_path).save(report)
        console.print(TextReportVisualizer().render(report))

        dashboard_path = DashboardVisualizer().render(report,output_dir / "dashboard.html",)

        console.print()
        console.print(f"[bold magenta]Dashboard generated:[/bold magenta] {dashboard_path}")            


        output_dir.mkdir(parents=True, exist_ok=True)
        if not no_replay:
            replay_path = ReplayExporter().export(trace, output_dir / "replay_frames.json")
            ReplayViewer().generate()
            console.print(f"[bold cyan]Replay frames exported:[/bold cyan] {replay_path}")

        if not no_graph:
            graph_path = TransitionGraphVisualizer().render(trace, output_dir / "transition_graph.html")
            console.print()
            console.print(f"[bold green]Transition graph saved:[/bold green] {graph_path}")

    except LocalityLensError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        log.exception("Unexpected failure during analysis")
        console.print(f"[bold red]Critical Error:[/bold red] {e}")
        raise typer.Exit(code=1)
