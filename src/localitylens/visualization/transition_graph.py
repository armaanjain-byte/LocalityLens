"""Interactive pyvis transition graph visualizer."""

from __future__ import annotations

import re
from collections import Counter
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


def cluster_name(path: str) -> str:
    path = path.lower()

    if "test" in path:
        return "TESTS"

    if "provider" in path:
        return "PROVIDERS"

    if "config" in path:
        return "CONFIG"

    if "parser" in path:
        return "PARSERS"

    if "semantic" in path:
        return "SEMANTIC"

    if "analysis" in path:
        return "ANALYSIS"

    if "visual" in path:
        return "VISUALIZATION"

    if "core" in path:
        return "CORE"

    return "OTHER"


class TransitionGraphVisualizer:
    """Render an interactive HTML transition graph from a Trace."""

    def render(
        self,
        trace: Trace,
        output_path: str | Path = "transition_graph.html",
    ) -> str:
        """Build and write an interactive HTML transition graph."""

        net = Network(
            height="900px",
            width="100%",
            bgcolor="#0d1117",
            font_color="#c9d1d9",
            directed=True,
        )

        edge_counter: Counter[tuple[str, str]] = Counter()
        node_visits: Counter[str] = Counter()

        sequence: list[str] = []
        for event in trace.events:
            target = display_target(event)
            if target:
                sequence.append(target)
                node_visits[target] += 1

        visible_nodes = {node for node, _count in node_visits.most_common(TOP_NODE_LIMIT)}

        previous: str | None = None
        for target in sequence:
            if target not in visible_nodes:
                continue
            if previous and previous != target:
                edge_counter[(previous, target)] += 1
            previous = target

        # ------------------------------------------------------------------
        # Add high-impact nodes
        # ------------------------------------------------------------------
        added_nodes: set[str] = set()

        for node, visits in node_visits.most_common(TOP_NODE_LIMIT):
            if node in added_nodes:
                continue

            added_nodes.add(node)

            if visits >= 40:
                color, size = "#da3633", 45
            elif visits >= 20:
                color, size = "#fb8500", 32
            elif visits >= 10:
                color, size = "#d29922", 24
            else:
                color, size = "#1f6feb", 14

            net.add_node(
                node,
                label=node,
                title=f"<b>{node}</b><br>Visits: {visits}",
                color=color,
                size=size,
            )

        # ------------------------------------------------------------------
        # Weighted edges with noise filtering
        # ------------------------------------------------------------------
        MIN_EDGE_WEIGHT = 3

        for (src, dst), weight in edge_counter.items():
            if weight < MIN_EDGE_WEIGHT:
                continue

            edge_width = min(1 + weight * 0.8, 12)

            edge_color = (
                "#da3633"
                if weight >= 10
                else "#fb8500"
                if weight >= 5
                else "#1f6feb"
            )

            net.add_edge(
                src,
                dst,
                value=weight,
                width=edge_width,
                color=edge_color,
                title=f"Transitions: {weight}",
            )

        # ------------------------------------------------------------------
        # Graph physics / interaction settings
        # ------------------------------------------------------------------
        net.set_options("""
        {
          "nodes": {
            "font": {
              "size": 14,
              "color": "#c9d1d9",
              "face": "Monaco, Menlo, monospace"
            }
          },

          "edges": {
            "color": {
              "color": "#30363d",
              "highlight": "#79c0ff"
            },
            "smooth": {
              "type": "continuous"
            }
          },

          "physics": {
            "forceAtlas2Based": {
              "gravitationalConstant": -250,
              "centralGravity": 0.015,
              "springLength": 120,
              "springConstant": 0.05
            },

            "solver": "forceAtlas2Based",

            "stabilization": {
              "iterations": 150
            }
          },

          "interaction": {
            "hover": true,
            "tooltipDelay": 100,
            "navigationButtons": false,
            "keyboard": true
          }
        }
        """)

        output = Path(output_path)

        net.write_html(str(output), notebook=False)

        return str(output)
