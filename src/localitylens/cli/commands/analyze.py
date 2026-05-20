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
    import math
    try:
        import networkx as nx
        _HAS_NX = True
    except ImportError:
        _HAS_NX = False

    node_visits: Counter[str] = Counter()
    node_reads: Counter[str] = Counter()
    node_writes: Counter[str] = Counter()
    edge_counter: Counter[tuple[str, str]] = Counter()
    previous: str | None = None
    sequence: list[str] = []

    for event in getattr(trace, "events", []):
        target = getattr(event, "target", None)
        if not target:
            continue
        t = str(target)
        node_visits[t] += 1
        kind_val = getattr(getattr(event, "kind", None), "value", "")
        if kind_val == "file_read":
            node_reads[t] += 1
        elif kind_val == "file_write":
            node_writes[t] += 1
        if previous and previous != t:
            edge_counter[(previous, t)] += 1
        previous = t
        sequence.append(t)

    # --- Per-node oscillation detection (A->B->A->B patterns) ---
    node_oscillations: Counter[str] = Counter()
    osc_edges: set[tuple[str, str]] = set()
    for i in range(len(sequence) - 3):
        a, b, c, d = sequence[i], sequence[i+1], sequence[i+2], sequence[i+3]
        if a == c and b == d and a != b:
            node_oscillations[a] += 1
            node_oscillations[b] += 1
            osc_edges.add((a, b))
            osc_edges.add((b, a))

    # --- Per-node reload detection (file re-accessed after leaving active window) ---
    node_reloads: Counter[str] = Counter()
    _window_size = 5
    from collections import deque
    active: deque[str] = deque(maxlen=_window_size)
    active_set: set[str] = set()
    evicted: set[str] = set()
    for t in sequence:
        if t in evicted and t not in active_set:
            node_reloads[t] += 1
            evicted.discard(t)
        if t in active_set:
            continue
        if len(active) == active.maxlen:
            removed = active.popleft()
            active_set.discard(removed)
            evicted.add(removed)
        active.append(t)
        active_set.add(t)

    # --- Compute thrash score per node (0-1 normalized) ---
    def thrash_score(node: str, visits: int) -> float:
        raw = node_oscillations[node] * 2 + node_reloads[node] * 1.5
        return min(1.0, raw / max(1, visits))

    # --- Build networkx graph for centrality ---
    betweenness: dict[str, float] = {}
    pagerank_scores: dict[str, float] = {}
    if _HAS_NX and edge_counter:
        G = nx.DiGraph()
        for (src, dst), w in edge_counter.items():
            G.add_edge(src, dst, weight=w)
        try:
            betweenness = nx.betweenness_centrality(G, weight="weight", normalized=True)
        except Exception:
            betweenness = {}
        try:
            pagerank_scores = nx.pagerank(G, weight="weight")
        except Exception:
            pagerank_scores = {}

    # Normalize centrality to 0-1
    max_btw = max(betweenness.values(), default=1) or 1
    max_pr = max(pagerank_scores.values(), default=1) or 1

    # --- Outgoing transition entropy per node ---
    node_entropy: dict[str, float] = {}
    for node in node_visits:
        out_edges = {dst: cnt for (src, dst), cnt in edge_counter.items() if src == node}
        total_out = sum(out_edges.values())
        if total_out > 1:
            entropy = -sum((c/total_out) * math.log2(c/total_out) for c in out_edges.values())
            node_entropy[node] = round(entropy, 4)
        else:
            node_entropy[node] = 0.0

    max_visits = max(node_visits.values(), default=1)
    nodes = []
    for node, visits in node_visits.most_common(TOP_NODE_LIMIT):
        ts = thrash_score(node, visits)
        # Size encodes attention (transition volume)
        size = 14 + min(36, int((visits / max_visits) * 36))

        # Color encodes churn severity
        if ts >= 0.7:
            color_bg = "#da3633"   # red: thrashing
            color_border = "#ff6b6b"
            churn_label = "thrashing"
        elif ts >= 0.4:
            color_bg = "#fb8500"   # orange: high churn
            color_border = "#ffa94d"
            churn_label = "high_churn"
        elif ts >= 0.2:
            color_bg = "#d29922"   # yellow: moderate churn
            color_border = "#ffd700"
            churn_label = "moderate_churn"
        elif ts >= 0.05:
            color_bg = "#1a7f37"   # green: mild churn
            color_border = "#3fb950"
            churn_label = "mild_churn"
        else:
            color_bg = "#1f6feb"   # blue: stable
            color_border = "#58a6ff"
            churn_label = "stable"

        # Border thickness encodes reload frequency
        border_width = 1 + min(5, node_reloads[node])

        btw_norm = round(betweenness.get(node, 0) / max_btw, 4)
        pr_norm = round(pagerank_scores.get(node, 0) / max_pr, 4)

        # Most common outgoing transition
        out_edges_sorted = sorted(
            [(dst, cnt) for (src, dst), cnt in edge_counter.items() if src == node],
            key=lambda x: -x[1]
        )
        most_common_transition = f"{node} → {out_edges_sorted[0][0]}" if out_edges_sorted else "none"

        # Generate behavioral explanation
        reasons = []
        if ts >= 0.5:
            reasons.append("Frequent context switching causes locality degradation")
        if node_reloads[node] > 3:
            reasons.append(f"Reloaded {node_reloads[node]}x after eviction from context")
        if node_oscillations[node] > 2:
            reasons.append(f"Detected {node_oscillations[node]} oscillation loops")
        if btw_norm > 0.5:
            reasons.append("High-betweenness routing bottleneck — agent repeatedly passes through this file")
        if pr_norm > 0.7:
            reasons.append("Dominant context anchor — high PageRank means attention concentrates here")
        if node_entropy.get(node, 0) > 2.0:
            reasons.append("High outgoing entropy indicates indecisive navigation from this file")
        if not reasons:
            reasons.append("Stable access pattern with low churn")

        nodes.append({
            "id": node,
            "label": node,
            "title": node,
            "value": visits,
            "size": size,
            "color": {
                "background": color_bg,
                "border": color_border,
                "highlight": {"background": color_bg, "border": "#ffffff"},
                "hover": {"background": color_bg, "border": "#ffffff"},
            },
            "borderWidth": border_width,
            "font": {"color": "#ffffff", "size": 11},
            # Behavioral data for explainability panel
            "_meta": {
                "visits": visits,
                "reads": node_reads[node],
                "writes": node_writes[node],
                "reloads": node_reloads[node],
                "oscillations": node_oscillations[node],
                "thrash_score": round(ts, 4),
                "churn_label": churn_label,
                "betweenness": btw_norm,
                "pagerank": pr_norm,
                "entropy": node_entropy.get(node, 0),
                "most_common_transition": most_common_transition,
                "explanation": ". ".join(reasons),
            },
        })

    visible_nodes = {n["id"] for n in nodes}
    max_weight = max(edge_counter.values(), default=1)

    edges = []
    for (src, dst), weight in edge_counter.most_common(150):
        if src not in visible_nodes or dst not in visible_nodes:
            continue

        # Thickness encodes frequency
        edge_width = min(1 + weight * 0.5, 12)

        # Color encodes stability
        is_osc = (src, dst) in osc_edges
        weight_ratio = weight / max_weight
        if is_osc:
            edge_color = "#da3633"    # red: oscillation loop
            edge_dashes = True
        elif weight_ratio > 0.5:
            edge_color = "#fb8500"    # orange: very high traffic
            edge_dashes = False
        elif weight_ratio > 0.2:
            edge_color = "#d29922"    # yellow: moderate traffic
            edge_dashes = False
        else:
            edge_color = "#1f6feb"    # blue: stable/rare
            edge_dashes = False

        edges.append({
            "id": f"{src}->{dst}",
            "from": src,
            "to": dst,
            "value": weight,
            "width": edge_width,
            "dashes": edge_dashes,
            "color": {"color": edge_color, "highlight": "#ffffff", "hover": "#ffffff"},
            "title": f"{src} → {dst}\nTransitions: {weight}" + (" [OSCILLATION LOOP]" if is_osc else ""),
            "_meta": {
                "weight": weight,
                "is_oscillation": is_osc,
                "weight_ratio": round(weight_ratio, 4),
            },
        })

    # --- Timeline heatmap: per-step churn signal for bottom strip ---
    timeline_data = []
    window = 50  # steps per bucket
    for i in range(0, len(sequence), window):
        bucket = sequence[i:i+window]
        if not bucket:
            break
        bucket_osc = sum(1 for j in range(len(bucket)-3)
                         if len(bucket) > j+3 and bucket[j] == bucket[j+2] and bucket[j+1] == bucket[j+3] and bucket[j] != bucket[j+1])
        unique_ratio = len(set(bucket)) / len(bucket)
        # churn_intensity: 0=stable, 1=chaotic
        churn_intensity = min(1.0, (bucket_osc / max(1, len(bucket)//4)) * 0.5 + (1 - unique_ratio) * 0.5)
        timeline_data.append(round(churn_intensity, 3))

    return {
        "nodes": nodes,
        "edges": edges,
        "limit": TOP_NODE_LIMIT,
        "timeline": timeline_data,
        "osc_edges": [{"from": s, "to": d} for s, d in osc_edges],
    }


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