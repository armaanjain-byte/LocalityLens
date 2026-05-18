"""CLI command to analyze a trace file."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from localitylens.analysis.anomaly import AnomalyAnalyzer
from localitylens.analysis.churn import ChurnAnalyzer
from localitylens.analysis.context_entropy import ContextEntropyAnalyzer
from localitylens.analysis.dependency_jump import DependencyJumpAnalyzer
from localitylens.analysis.locality import LocalityAnalyzer
from localitylens.analysis.semantic_continuity import SemanticContinuityAnalyzer
from localitylens.analysis.thrashing import ThrashingAnalyzer
from localitylens.analysis.transition_graph import TransitionGraphAnalyzer
from localitylens.analysis.waste import WasteAnalyzer
from localitylens.core.exceptions import LocalityLensError, UnsupportedFormatError
from localitylens.core.metrics import AnalysisReport
from localitylens.core.semantic_map import SemanticMap
from localitylens.core.trace import Trace
from localitylens.parsers.claude_code import ClaudeCodeParser
from localitylens.parsers.generic_json import GenericJsonParser
from localitylens.semantic.mapper import SemanticMapper
from localitylens.storage.db import ReportStore
from localitylens.utils.logger import get_logger
from localitylens.utils.validators import validate_file_exists
from localitylens.visualization.charts import TextReportVisualizer
from localitylens.visualization.replay_export import ReplayExporter
from localitylens.visualization.transition_graph import TransitionGraphVisualizer

app = typer.Typer()
log = get_logger(__name__)
console = Console()

PARSERS = [ClaudeCodeParser(), GenericJsonParser()]

# All analyzers now share the unified signature:
#   analyze(trace: Trace, smap: SemanticMap, report: AnalysisReport) -> None
# No runtime introspection needed — see each analyzer's updated signature.
ANALYZERS = [
    AnomalyAnalyzer(),
    SemanticContinuityAnalyzer(),
    DependencyJumpAnalyzer(),
    ContextEntropyAnalyzer(),
    TransitionGraphAnalyzer(),
    ChurnAnalyzer(),
    ThrashingAnalyzer(),
    WasteAnalyzer(),
    LocalityAnalyzer(),
]


@app.command("file")
def analyze_file(
    trace_path: Path = typer.Argument(..., help="Path to the agent trace file"),
    db_path: Path = typer.Option(Path("localitylens.db"), help="Path to SQLite database"),
) -> None:
    """Analyze a single trace file and display the report."""
    try:
        # 1. Validation
        validate_file_exists(trace_path)

        # 2. Parsing
        parser = next((p for p in PARSERS if p.can_parse(trace_path)), None)
        if not parser:
            raise UnsupportedFormatError(f"No parser found for file: {trace_path.name}")

        console.print(f"[bold blue]Parsing[/bold blue] {trace_path.name} using {parser.format.value}...")
        trace: Trace = parser.parse(trace_path)

        # 3. Semantic Mapping
        smap: SemanticMap = SemanticMapper().build(trace)

        # 4. Analysis — unified signature: analyze(trace, smap, report)
        report = AnalysisReport(trace_id=trace.trace_id)
        for analyzer in ANALYZERS:
            analyzer.analyze(trace, smap, report)
        report.sort_metrics()

        # 5. Storage
        ReportStore(db_path).save(report)

        # 6. Visualization
        console.print(TextReportVisualizer().render(report))

        graph_path = TransitionGraphVisualizer().render(trace)   # separate var — do NOT shadow trace_path
        replay_path = ReplayExporter().export(trace)

        console.print(f"[bold cyan]Replay frames exported:[/bold cyan] {replay_path}")
        console.print()
        console.print(f"[bold green]Transition graph saved:[/bold green] {graph_path}")

    except LocalityLensError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        log.exception("Unexpected failure during analysis")
        console.print(f"[bold red]Critical Error:[/bold red] {e}")
        raise typer.Exit(code=1)