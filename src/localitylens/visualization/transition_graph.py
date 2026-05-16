from collections import Counter, defaultdict

from pyvis.network import Network


class TransitionGraphVisualizer:
    """Interactive transition graph for repository movement."""

    def render(self, trace, output_path="transition_graph.html"):
        net = Network(
            height="900px",
            width="100%",
            bgcolor="#0b1020",
            font_color="white",
            directed=True,
        )

        edge_counter = Counter()
        node_visits = Counter()

        previous = None

        # ---------------------------------------------------
        # Build transition frequencies
        # ---------------------------------------------------

        for event in trace.events:
            target = getattr(event, "target", None)

            if not target:
                continue

            node_visits[target] += 1

            if previous:
                edge_counter[(previous, target)] += 1

            previous = target

        # ---------------------------------------------------
        # Add nodes with severity coloring
        # ---------------------------------------------------

        for node, visits in node_visits.items():

            # Severity coloring
            if visits >= 40:
                color = "#ff3b3b"
                size = 45

            elif visits >= 20:
                color = "#ff944d"
                size = 32

            elif visits >= 10:
                color = "#ffd24d"
                size = 24

            else:
                color = "#66b3ff"
                size = 14

            title = f"""
            <b>{node}</b><br>
            Visits: {visits}
            """

            net.add_node(
                node,
                label=node.split("/")[-1],
                title=title,
                color=color,
                size=size,
            )

        # ---------------------------------------------------
        # Add weighted edges
        # ---------------------------------------------------

        for (src, dst), weight in edge_counter.items():

            edge_width = min(1 + weight * 0.8, 12)

            if weight >= 10:
                edge_color = "#ff5555"

            elif weight >= 5:
                edge_color = "#ffaa55"

            else:
                edge_color = "#4a90e2"

            net.add_edge(
                src,
                dst,
                value=weight,
                width=edge_width,
                color=edge_color,
                title=f"Transitions: {weight}",
            )

        # ---------------------------------------------------
        # Physics tuning
        # ---------------------------------------------------

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
              "gravitationalConstant": -120,
              "centralGravity": 0.015,
              "springLength": 180,
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

        net.write_html(output_path, notebook=False)

        return output_path