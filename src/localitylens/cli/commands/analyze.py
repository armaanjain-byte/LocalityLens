"""CLI command to analyze a trace file."""

from pathlib import Path
from typing import List

import typer
from localitylens.analysis.anomaly import AnomalyAnalyzer
from localitylens.visualization.replay_export import ReplayExporter
from rich.console import Console
from localitylens.analysis.semantic_continuity import SemanticContinuityAnalyzer
from localitylens.analysis.transition_graph import TransitionGraphAnalyzer
from localitylens.analysis.churn import ChurnAnalyzer
from localitylens.analysis.locality import LocalityAnalyzer
from localitylens.analysis.thrashing import ThrashingAnalyzer
from localitylens.analysis.waste import WasteAnalyzer
from localitylens.core.exceptions import LocalityLensError, UnsupportedFormatError
from localitylens.core.metrics import AnalysisReport
from localitylens.parsers.claude_code import ClaudeCodeParser
from localitylens.parsers.generic_json import GenericJsonParser
from localitylens.semantic.mapper import SemanticMapper
from localitylens.storage.db import ReportStore
from localitylens.utils.logger import get_logger
from localitylens.utils.validators import validate_file_exists
from localitylens.visualization.charts import TextReportVisualizer
from localitylens.analysis.context_entropy import ContextEntropyAnalyzer
from localitylens.analysis.dependency_jump import DependencyJumpAnalyzer
from localitylens.visualization.transition_graph import (
    TransitionGraphVisualizer,
)
app = typer.Typer()
log = get_logger(__name__)
console = Console()

# Initialise components
PARSERS = [ClaudeCodeParser(), GenericJsonParser()]
ANALYZERS = [
    AnomalyAnalyzer(),
    SemanticContinuityAnalyzer(),
    DependencyJumpAnalyzer(),
    ContextEntropyAnalyzer(),
    TransitionGraphAnalyzer(),
    ChurnAnalyzer(),
    ThrashingAnalyzer(),
    WasteAnalyzer(),
]


@app.command("file")
def analyze_file(
    path: Path = typer.Argument(..., help="Path to the agent trace file"),
    db_path: Path = typer.Option(Path("localitylens.db"), help="Path to SQLite database"),
) -> None:
    """Analyze a single trace file and display the report."""
    try:
        # 1. Validation
        validate_file_exists(path)

        # 2. Parsing
        parser = next((p for p in PARSERS if p.can_parse(path)), None)
        if not parser:
            raise UnsupportedFormatError(f"No parser found for file: {path.name}")

        console.print(f"[bold blue]Parsing[/bold blue] {path.name} using {parser.format.value}...")
        trace = parser.parse(path)

        # 3. Semantic Mapping
        mapper = SemanticMapper()
        smap = mapper.build(trace)

        # 4. Analysis
        report = AnalysisReport(trace_id=trace.trace_id)
        for analyzer in ANALYZERS:
            # Note: Different analyzers require different data (Trace vs SemanticMap)
            if hasattr(analyzer, "analyze"):
                # Pass smap or trace based on signature
                import inspect

                sig = inspect.signature(analyzer.analyze)
                if "smap" in sig.parameters:
                    analyzer.analyze(smap, report)
                else:
                    analyzer.analyze(trace, report)
        report.sort_metrics()
        # 5. Storage
        store = ReportStore(db_path)
        store.save(report)

        # 6. Visualization
        visualizer = TextReportVisualizer()
        console.print(visualizer.render(report))
        graph = TransitionGraphVisualizer()

        path = graph.render(trace)
        replay = ReplayExporter()

        replay_path = replay.export(trace)

        console.print(
    f"[bold cyan]Replay frames exported:[/bold cyan] {replay_path}"
)
        console.print()
        console.print(
             f"[bold green]Transition graph saved:[/bold green] {path}"
        )       

    except LocalityLensError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        log.exception("Unexpected failure during analysis")
        console.print(f"[bold red]Critical Error:[/bold red] {e}")
        raise typer.Exit(code=1)