"""Interactive behavioral transition graph visualizer."""

from __future__ import annotations

import math
import re
from collections import Counter, deque
from pathlib import Path

from pyvis.network import Network  # type: ignore[import-untyped]

from localitylens.core.trace import Trace

TOP_NODE_LIMIT = 30
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\[[0-9;]*m")


def display_target(event: object) -> str | None:
    target = getattr(event, "target", None)
    if not target:
        return None
    target_text = _ANSI_RE.sub("", str(target)).strip()
    if target_text.lower() == "other":
        kind = getattr(getattr(event, "kind", None), "value", str(getattr(event, "kind", "unknown")))
        return f"[{kind}]"
    return target_text


def _compute_node_metrics(
    sequence: list[str],
    node_reads: Counter[str],
    node_writes: Counter[str],
) -> dict[str, dict]:
    """Compute per-node behavioral metrics: reloads, oscillations, thrash score."""
    node_oscillations: Counter[str] = Counter()
    osc_pairs: set[tuple[str, str]] = set()
    for i in range(len(sequence) - 3):
        a, b, c, d = sequence[i], sequence[i+1], sequence[i+2], sequence[i+3]
        if a == c and b == d and a != b:
            node_oscillations[a] += 1
            node_oscillations[b] += 1
            osc_pairs.add((a, b))
            osc_pairs.add((b, a))

    node_reloads: Counter[str] = Counter()
    active: deque[str] = deque(maxlen=5)
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

    metrics: dict[str, dict] = {}
    for node in set(sequence):
        visits = sequence.count(node)
        raw = node_oscillations[node] * 2 + node_reloads[node] * 1.5
        ts = min(1.0, raw / max(1, visits))
        metrics[node] = {
            "visits": visits,
            "reads": node_reads[node],
            "writes": node_writes[node],
            "oscillations": node_oscillations[node],
            "reloads": node_reloads[node],
            "thrash_score": round(ts, 3),
        }
    return metrics, osc_pairs


def _churn_color(thrash_score: float) -> tuple[str, str]:
    """Return (bg_color, border_color) for a thrash score 0-1."""
    if thrash_score >= 0.7:
        return "#da3633", "#ff6b6b"
    elif thrash_score >= 0.4:
        return "#fb8500", "#ffa94d"
    elif thrash_score >= 0.2:
        return "#d29922", "#ffd700"
    elif thrash_score >= 0.05:
        return "#1a7f37", "#3fb950"
    else:
        return "#1f6feb", "#58a6ff"


class TransitionGraphVisualizer:
    """Render an interactive behavioral HTML transition graph from a Trace."""

    def render(
        self,
        trace: Trace,
        output_path: str | Path = "transition_graph.html",
    ) -> str:
        """Build and write an interactive behavioral HTML transition graph."""

        net = Network(
            height="100vh",
            width="100%",
            bgcolor="#0d1117",
            font_color="#c9d1d9",
            directed=True,
        )

        node_visits: Counter[str] = Counter()
        node_reads: Counter[str] = Counter()
        node_writes: Counter[str] = Counter()
        edge_counter: Counter[tuple[str, str]] = Counter()
        sequence: list[str] = []

        for event in trace.events:
            target = display_target(event)
            if not target:
                continue
            sequence.append(target)
            node_visits[target] += 1
            kind_val = getattr(getattr(event, "kind", None), "value", "")
            if kind_val == "file_read":
                node_reads[target] += 1
            elif kind_val == "file_write":
                node_writes[target] += 1

        visible_nodes = {node for node, _ in node_visits.most_common(TOP_NODE_LIMIT)}

        previous: str | None = None
        for target in sequence:
            if target not in visible_nodes:
                continue
            if previous and previous != target:
                edge_counter[(previous, target)] += 1
            previous = target

        # Compute behavioral metrics
        node_metrics, osc_pairs = _compute_node_metrics(
            [t for t in sequence if t in visible_nodes],
            node_reads,
            node_writes,
        )

        # --- Centrality via networkx (optional) ---
        betweenness: dict[str, float] = {}
        pagerank_scores: dict[str, float] = {}
        try:
            import networkx as nx
            G = nx.DiGraph()
            for (src, dst), w in edge_counter.items():
                G.add_edge(src, dst, weight=w)
            betweenness = nx.betweenness_centrality(G, weight="weight", normalized=True)
            pagerank_scores = nx.pagerank(G, weight="weight")
        except Exception:
            pass

        max_btw = max(betweenness.values(), default=1) or 1
        max_pr = max(pagerank_scores.values(), default=1) or 1

        # --- Add nodes with behavioral encoding ---
        max_visits = max(node_visits.values(), default=1)
        added_nodes: set[str] = set()

        for node, visits in node_visits.most_common(TOP_NODE_LIMIT):
            if node in added_nodes:
                continue
            added_nodes.add(node)

            meta = node_metrics.get(node, {})
            ts = meta.get("thrash_score", 0.0)
            color_bg, color_border = _churn_color(ts)

            # Size = attention volume
            size = 12 + min(38, int((visits / max_visits) * 38))
            # Border thickness = reload frequency
            border_width = 1 + min(5, meta.get("reloads", 0))

            btw = round(betweenness.get(node, 0) / max_btw, 3)
            pr = round(pagerank_scores.get(node, 0) / max_pr, 3)

            # Tooltip
            churn_label = (
                "🔴 THRASHING" if ts >= 0.7 else
                "🟠 HIGH CHURN" if ts >= 0.4 else
                "🟡 MODERATE" if ts >= 0.2 else
                "🟢 MILD" if ts >= 0.05 else
                "🔵 STABLE"
            )

            tooltip = (
                f"<b>{node}</b><br>"
                f"Status: {churn_label}<br>"
                f"Visits: {visits} | Reads: {meta.get('reads',0)} | Writes: {meta.get('writes',0)}<br>"
                f"Reloads: {meta.get('reloads',0)} | Oscillations: {meta.get('oscillations',0)}<br>"
                f"Thrash score: {ts:.3f}<br>"
                f"Betweenness: {btw:.3f} | PageRank: {pr:.3f}"
            )

            net.add_node(
                node,
                label=node,
                title=tooltip,
                color={"background": color_bg, "border": color_border,
                       "highlight": {"background": color_bg, "border": "#ffffff"}},
                size=size,
                borderWidth=border_width,
                font={"color": "#ffffff", "size": 11},
            )

        # --- Add edges with behavioral encoding ---
        max_weight = max(edge_counter.values(), default=1)
        MIN_EDGE_WEIGHT = 2

        for (src, dst), weight in edge_counter.items():
            if weight < MIN_EDGE_WEIGHT:
                continue
            if src not in added_nodes or dst not in added_nodes:
                continue

            edge_width = min(1 + weight * 0.6, 12)
            is_osc = (src, dst) in osc_pairs
            weight_ratio = weight / max_weight

            if is_osc:
                edge_color = "#da3633"
                dashes = True
            elif weight_ratio > 0.5:
                edge_color = "#fb8500"
                dashes = False
            elif weight_ratio > 0.2:
                edge_color = "#d29922"
                dashes = False
            else:
                edge_color = "#1f6feb"
                dashes = False

            edge_title = f"{src} → {dst}<br>Transitions: {weight}"
            if is_osc:
                edge_title += "<br><b>⚠ OSCILLATION LOOP</b>"

            net.add_edge(
                src,
                dst,
                value=weight,
                width=edge_width,
                color=edge_color,
                title=edge_title,
                dashes=dashes,
            )

        net.set_options("""
        {
          "nodes": {
            "font": {
              "size": 11,
              "color": "#c9d1d9",
              "face": "Monaco, Menlo, monospace"
            }
          },
          "edges": {
            "color": {
              "color": "#30363d",
              "highlight": "#ffffff"
            },
            "smooth": {
              "type": "dynamic"
            },
            "arrows": {
              "to": { "enabled": true, "scaleFactor": 0.45 }
            }
          },
          "physics": {
            "forceAtlas2Based": {
              "gravitationalConstant": -280,
              "centralGravity": 0.012,
              "springLength": 130,
              "springConstant": 0.06,
              "damping": 0.4,
              "avoidOverlap": 0.5
            },
            "solver": "forceAtlas2Based",
            "stabilization": { "iterations": 180 },
            "timestep": 0.35
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 80,
            "navigationButtons": false,
            "keyboard": true
          }
        }
        """)

        output = Path(output_path)
        net.write_html(str(output), notebook=False)
        return str(output)