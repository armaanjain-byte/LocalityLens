"""CLI command to analyze a trace file."""

from __future__ import annotations
import webbrowser
import os
import json
import copy
import re
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from localitylens.core.exceptions import LocalityLensError, UnsupportedFormatError
from localitylens.core.metrics import AnalysisReport
from localitylens.core.trace import Trace
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
TOP_NODE_LIMIT = 30
REPLAY_FRAME_LIMIT = 5_000
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\[[0-9;]*m")


def _strip_ansi(value: str) -> str:
    return _ANSI_RE.sub("", value)


def _json_default(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "value"):
        return getattr(value, "value")
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


def _json_for_script(value: object) -> str:
    """Serialize JSON for a script[type=application/json] block."""
    return json.dumps(value, default=_json_default).replace("</", "<\\/")


def _metric_payload(report: AnalysisReport) -> dict[str, Any]:
    metrics = []
    for metric in getattr(report, "metrics", []):
        metrics.append(
            {
                "name": metric.name,
                "value": metric.value,
                "severity": getattr(metric.severity, "value", str(metric.severity)),
                "details": _strip_ansi(metric.details or ""),
                "extra": metric.extra,
            }
        )
    return {
        "trace_id": getattr(report, "trace_id", ""),
        "summary": _strip_ansi(getattr(report, "summary", "") or ""),
        "metrics": metrics,
        "anomalies": getattr(report, "anomalies", []),
    }


def _display_target(event: object) -> str | None:
    target = getattr(event, "target", None)
    if not target:
        return None
    target_text = _strip_ansi(str(target)).strip()
    if target_text.lower() == "other":
        kind = getattr(getattr(event, "kind", None), "value", str(getattr(event, "kind", "unknown")))
        return f"[{kind}]"
    return target_text


def _focused_trace(trace: Trace) -> Trace:
    ui_events = []
    node_visits: Counter[str] = Counter()

    for event in getattr(trace, "events", []):
        target = _display_target(event)
        if not target:
            continue
        ev = copy.copy(event)
        ev.target = target
        ui_events.append(ev)
        node_visits[target] += 1

    top_nodes = {node for node, _count in node_visits.most_common(TOP_NODE_LIMIT)}
    filtered_events = [ev for ev in ui_events if getattr(ev, "target", None) in top_nodes]

    ui_trace = copy.copy(trace)
    ui_trace.events = filtered_events
    return ui_trace


def _graph_payload(trace: Trace) -> dict[str, Any]:
    node_visits: Counter[str] = Counter()
    edge_counter: Counter[tuple[str, str]] = Counter()
    previous: str | None = None

    for event in getattr(trace, "events", []):
        target = getattr(event, "target", None)
        if not target:
            continue
        node_visits[str(target)] += 1
        if previous and previous != target:
            edge_counter[(previous, str(target))] += 1
        previous = str(target)

    max_visits = max(node_visits.values(), default=1)
    nodes = []
    for node, visits in node_visits.most_common(TOP_NODE_LIMIT):
        size = 18 + min(30, int((visits / max_visits) * 30))
        nodes.append(
            {
                "id": node,
                "label": node,
                "title": f"{node}\nVisits: {visits}",
                "value": visits,
                "size": size,
            }
        )

    visible_nodes = {node["id"] for node in nodes}
    edges = [
        {
            "id": f"{src}->{dst}",
            "from": src,
            "to": dst,
            "label": str(weight),
            "value": weight,
            "title": f"{src} -> {dst}\nTransitions: {weight}",
            "width": min(1 + weight * 0.35, 10),
        }
        for (src, dst), weight in edge_counter.most_common(120)
        if src in visible_nodes and dst in visible_nodes
    ]

    return {"nodes": nodes, "edges": edges, "limit": TOP_NODE_LIMIT}


def _replay_payload(trace: Trace) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    previous: str | None = None

    for idx, event in enumerate(getattr(trace, "events", [])):
        if len(frames) >= REPLAY_FRAME_LIMIT:
            break
        target = getattr(event, "target", None)
        if not target:
            continue
        if previous is not None and previous != target:
            raw_ts = getattr(event, "timestamp", idx)
            frames.append(
                {
                    "step": idx,
                    "timestamp": _json_default(raw_ts),
                    "from": previous,
                    "to": str(target),
                    "event_type": getattr(getattr(event, "kind", None), "value", "unknown"),
                }
            )
        previous = str(target)

    return frames

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
        
        # 1. Core Metrics
        report = analyze_trace(trace, smap)
        ReportStore(db_path).save(report)
        
        capture_console = Console(record=True, force_terminal=False)
        rendered_report = TextReportVisualizer().render(report)
        capture_console.print(rendered_report)
        
        report_text = capture_console.export_text() 
        report_text = _strip_ansi(report_text)
        
        console.print(rendered_report)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. Browser payloads
        ui_trace = _focused_trace(trace)
        metrics_data = _metric_payload(report)
        metrics_data["report_text"] = report_text
        graph_data = _graph_payload(ui_trace)
        replay_data = _replay_payload(ui_trace)

        # 3. Standalone transition graph
        if not no_graph:
            graph_path = TransitionGraphVisualizer().render(ui_trace, output_dir / "transition_graph.html")
            console.print(f"[bold green]Transition graph saved:[/bold green] {graph_path}")

        # 4. Inject safe JSON into the dashboard
        template_path = (
            Path(__file__).resolve().parents[2]
            / "visualization"
            / "html_templates"
            / "dashboard_template.html"
        )
        if template_path.exists():
            html_content = template_path.read_text(encoding="utf-8")
            html_content = html_content.replace("{{ METRICS_DATA }}", _json_for_script(metrics_data))
            html_content = html_content.replace("{{ GRAPH_DATA }}", _json_for_script(graph_data))
            html_content = html_content.replace("{{ REPLAY_JSON_DATA }}", _json_for_script(replay_data))

            dashboard_file = output_dir / "localitylens_dashboard.html"
            dashboard_file.write_text(html_content, encoding="utf-8")

            console.print("\n[bold magenta]Interactive Dashboard generated successfully![/bold magenta]")
            absolute_path = f"file://{os.path.abspath(dashboard_file)}"
            webbrowser.open(absolute_path)
        else:
            console.print(f"[bold yellow]Warning: Template not found at {template_path}.[/bold yellow]")

        if not no_replay:
            replay_path = ReplayExporter().export(ui_trace, output_dir / "replay_frames.json")
            console.print(f"[bold cyan]Replay frames exported:[/bold cyan] {replay_path}")

    except LocalityLensError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        log.exception("Unexpected failure during analysis")
        console.print(f"[bold red]Critical Error:[/bold red] {e}")
        raise typer.Exit(code=1)
