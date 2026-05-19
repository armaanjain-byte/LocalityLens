"""Interactive pyvis transition graph visualizer."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from pyvis.network import Network  # type: ignore[import-untyped]

from localitylens.core.trace import Trace


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
            bgcolor="#0b1020",
            font_color="white",
            directed=True,
        )

        edge_counter: Counter[tuple[str, str]] = Counter()
        node_visits: Counter[str] = Counter()

        previous: str | None = None

        # ------------------------------------------------------------------
        # Build clustered transition graph
        # ------------------------------------------------------------------
        for event in trace.events:
            target = getattr(event, "target", None)

            if not target:
                continue

            current_cluster = cluster_name(target)

            node_visits[current_cluster] += 1

            if previous:
                previous_cluster = cluster_name(previous)

                edge_counter[(previous_cluster, current_cluster)] += 1

            previous = target

        # ------------------------------------------------------------------
        # Add clustered nodes
        # ------------------------------------------------------------------
        added_nodes: set[str] = set()

        for node, visits in node_visits.items():
            if node in added_nodes:
                continue

            added_nodes.add(node)

            if visits >= 40:
                color, size = "#ff3b3b", 45
            elif visits >= 20:
                color, size = "#ff944d", 32
            elif visits >= 10:
                color, size = "#ffd24d", 24
            else:
                color, size = "#66b3ff", 14

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
                "#ff5555"
                if weight >= 10
                else "#ffaa55"
                if weight >= 5
                else "#4a90e2"
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
              "size": 14
            }
          },

          "edges": {
            "smooth": {
              "type": "dynamic"
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
            "navigationButtons": true,
            "keyboard": true
          }
        }
        """)

        output = Path(output_path)

        net.write_html(str(output), notebook=False)

        return str(output)