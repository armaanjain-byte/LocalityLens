
from collections import Counter
from pathlib import Path

from pyvis.network import Network

from localitylens.utils.filters import is_real_file_target


class TransitionGraphVisualizer:
    """Interactive behavioral workflow graph."""

    def render(
        self,
        trace,
        output_path="transition_graph.html",
    ):

        net = Network(
            height="1000px",
            width="100%",
            bgcolor="#020817",
            font_color="white",
            directed=True,
            notebook=False,
        )

        edge_counter = Counter()
        node_visits = Counter()

        previous = None

        # ---------------------------------------------------
        # Build transition frequencies
        # ---------------------------------------------------

        for event in trace.events:

            target = getattr(event, "target", None)

            if (
                not target
                or not is_real_file_target(target)
            ):
                continue

            node_visits[target] += 1

            if previous:
                edge_counter[(previous, target)] += 1

            previous = target

        # ---------------------------------------------------
        # Hotspot extraction
        # ---------------------------------------------------

        top_hotspots = node_visits.most_common(5)

        hotspot_html = "".join(
            f"<div class='hotspot-item'>"
            f"<span>{idx + 1}. {node.split('/')[-1]}</span>"
            f"<span>{count}</span>"
            f"</div>"
            for idx, (node, count)
            in enumerate(top_hotspots)
        )

        # ---------------------------------------------------
        # Node categorization
        # ---------------------------------------------------

        def classify_node(node: str):

            lowered = node.lower()

            if "test" in lowered:
                return "tests", "#a855f7", "Test Module"

            if (
                "config" in lowered
                or "settings" in lowered
                or lowered.endswith(".json")
                or lowered.endswith(".yaml")
                or lowered.endswith(".yml")
            ):
                return "config", "#06b6d4", "Configuration"

            if (
                "util" in lowered
                or "helper" in lowered
                or "common" in lowered
            ):
                return "utils", "#10b981", "Utility Module"

            return "core", "#60a5fa", "Core Source"

        # ---------------------------------------------------
        # Add nodes
        # ---------------------------------------------------

        for node, visits in node_visits.items():

            group, base_color, category = classify_node(node)

            if visits >= 40:
                size = 54
                border = "#ff3b3b"
                activity = "High Instability"
                mass = 4

            elif visits >= 20:
                size = 38
                border = "#ff944d"
                activity = "Moderate Instability"
                mass = 2.5

            elif visits >= 10:
                size = 24
                border = "#ffd24d"
                activity = "Active Context"
                mass = 1.8

            else:
                size = 10
                border = "#1e3a8a"
                activity = "Low Activity"
                mass = 1

            title = f"""
            <div style="padding:12px; min-width:240px; font-family:Inter,sans-serif;">

                <div style="font-size:16px; font-weight:700; margin-bottom:8px; color:#ffffff;">
                    {node}
                </div>

                <div style="margin-bottom:4px; color:#cbd5e1;">
                    <b>Visits:</b> {visits}
                </div>

                <div style="margin-bottom:4px; color:#cbd5e1;">
                    <b>Category:</b> {category}
                </div>

                <div style="margin-bottom:4px; color:#cbd5e1;">
                    <b>Behavior:</b> {activity}
                </div>

                <div style="color:#cbd5e1;">
                    <b>Workflow Density:</b>
                    {'High' if visits >= 20 else 'Moderate' if visits >= 10 else 'Low'}
                </div>

            </div>
            """

            net.add_node(
                node,
                label="",
                title=title,
                shape="dot",
                size=size,
                mass=mass,
                group=group,
                borderWidth=2,
                color={
                    "background": base_color,
                    "border": border,
                    "highlight": {
                        "background": "#ffffff",
                        "border": "#ff3b3b",
                    },
                    "hover": {
                        "background": "#ffffff",
                        "border": border,
                    },
                },
            )

        # ---------------------------------------------------
        # Add edges
        # ---------------------------------------------------

        for (src, dst), weight in edge_counter.items():

            if weight >= 10:
                edge_color = "#ff5555"
                edge_opacity = 1.0
                edge_width = 10
                strength = "Strong Workflow Loop"

            elif weight >= 5:
                edge_color = "#ffaa55"
                edge_opacity = 0.8
                edge_width = 6
                strength = "Moderate Workflow Loop"

            elif weight >= 2:
                edge_color = "#4a90e2"
                edge_opacity = 0.35
                edge_width = 2
                strength = "Weak Workflow Link"

            else:
                edge_color = "#22304a"
                edge_opacity = 0.14
                edge_width = 1
                strength = "Transient Jump"

            net.add_edge(
                src,
                dst,
                value=weight,
                width=edge_width,
                smooth={
                    "enabled": True,
                    "type": "dynamic",
                    "roundness": 0.18,
                },
                color={
                    "color": edge_color,
                    "opacity": edge_opacity,
                    "highlight": "#ffffff",
                    "hover": "#ffffff",
                },
                title=(
                    f"<div style='padding:10px;'>"
                    f"<b>{src.split('/')[-1]}</b> → "
                    f"<b>{dst.split('/')[-1]}</b><br><br>"
                    f"Transitions: {weight}<br>"
                    f"Workflow Strength: {strength}"
                    f"</div>"
                ),
            )

        # ---------------------------------------------------
        # Physics + interaction tuning
        # ---------------------------------------------------

        net.set_options("""
        {
          "nodes": {
            "font": {
              "size": 0
            }
          },

          "edges": {
            "selectionWidth": 2,
            "smooth": {
              "enabled": true,
              "type": "dynamic"
            }
          },

          "groups": {
            "tests": {
              "shape": "dot"
            },

            "config": {
              "shape": "dot"
            },

            "utils": {
              "shape": "dot"
            },

            "core": {
              "shape": "dot"
            }
          },

          "physics": {
            "enabled": true,

            "forceAtlas2Based": {
              "gravitationalConstant": -420,
              "centralGravity": 0.004,
              "springLength": 360,
              "springConstant": 0.018,
              "damping": 0.94,
              "avoidOverlap": 1
            },

            "solver": "forceAtlas2Based",

            "stabilization": {
              "enabled": true,
              "iterations": 600,
              "updateInterval": 25
            }
          },

          "interaction": {
            "hover": true,
            "hoverConnectedEdges": true,
            "tooltipDelay": 100,
            "navigationButtons": true,
            "keyboard": true,
            "zoomView": true,
            "dragView": true,
            "multiselect": true
          }
        }
        """)

        html = net.generate_html(notebook=False)

        html = html.replace(
            "{{HOTSPOTS}}",
            hotspot_html,
        )

        template_path = (
            Path(__file__).parent
            / "html_templates"
            / "graph_template.html"
        )

        template = template_path.read_text(encoding="utf-8")

        final_html = template.replace(
            "{{GRAPH_CONTENT}}",
            html,
        )

        Path(output_path).write_text(
            final_html,
            encoding="utf-8",
        )

        return output_path
