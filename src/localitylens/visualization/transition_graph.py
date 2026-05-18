"""Interactive pyvis transition graph visualizer."""

from __future__ import annotations

from collections import Counter

from pyvis.network import Network

from localitylens.core.trace import Trace


class TransitionGraphVisualizer:
    """Render an interactive HTML transition graph from a Trace."""

    def render(self, trace: Trace, output_path: str = "transition_graph.html") -> str:
        """Build and write an interactive HTML transition graph.

        Args:
            trace:       The trace to visualize.
            output_path: Destination HTML file path (default: transition_graph.html).

        Returns:
            The output_path string so callers can log or display it.
        """
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

        for event in trace.events:
            target = getattr(event, "target", None)
            if not target:
                continue

            node_visits[target] += 1

            if previous:
                edge_counter[(previous, target)] += 1

            previous = target

        # ------------------------------------------------------------------
        # Nodes with visit-frequency colour coding
        # ------------------------------------------------------------------
        for node, visits in node_visits.items():
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
                label=node.split("/")[-1],
                title=f"<b>{node}</b><br>Visits: {visits}",
                color=color,
                size=size,
            )

        # ------------------------------------------------------------------
        # Weighted edges
        # ------------------------------------------------------------------
        for (src, dst), weight in edge_counter.items():
            edge_width = min(1 + weight * 0.8, 12)
            edge_color = "#ff5555" if weight >= 10 else "#ffaa55" if weight >= 5 else "#4a90e2"
            net.add_edge(
                src,
                dst,
                value=weight,
                width=edge_width,
                color=edge_color,
                title=f"Transitions: {weight}",
            )

        net.set_options("""
        {
          "nodes": { "font": { "size": 14 } },
          "edges": { "smooth": { "type": "dynamic" } },
          "physics": {
            "forceAtlas2Based": {
              "gravitationalConstant": -120,
              "centralGravity": 0.015,
              "springLength": 180,
              "springConstant": 0.05
            },
            "solver": "forceAtlas2Based",
            "stabilization": { "iterations": 150 }
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 100,
            "navigationButtons": true,
            "keyboard": true
          }
        }
        """)

        net.write_html(output_path, notebook=False)
        return output_path