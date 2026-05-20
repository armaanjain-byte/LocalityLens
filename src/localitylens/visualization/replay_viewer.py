"""Replay viewer HTML generator."""

from __future__ import annotations

from pathlib import Path


class ReplayViewer:
    """Generate replay HTML viewer."""

    def generate(
        self,
        output_path: str | Path = "replay_viewer.html",
    ) -> str:
        output = Path(output_path)

        html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>LocalityLens Replay</title>

<style>
body {
    margin: 0;
    background: #0b1020;
    color: white;
    font-family: Arial, sans-serif;
}

header {
    padding: 16px;
    background: #111827;
    border-bottom: 1px solid #333;
}

#viewer {
    width: 100vw;
    height: calc(100vh - 80px);
}
</style>

<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
</head>

<body>

<header>
<h2>LocalityLens Replay Viewer</h2>
<button onclick="toggleReplay()">Play / Pause</button>
</header>

<div id="viewer"></div>

<script>
let frames = [];
let frameIndex = 0;
let playing = true;

const nodes = new vis.DataSet([]);
const edges = new vis.DataSet([]);

const container = document.getElementById("viewer");

const data = {
    nodes: nodes,
    edges: edges
};

const options = {
    physics: {
        stabilization: false,
        barnesHut: {
            gravitationalConstant: -3000,
            springLength: 120
        }
    },
    nodes: {
        color: "#66b3ff",
        font: {
            color: "white"
        }
    },
    edges: {
        color: "#4a90e2",
        arrows: "to"
    }
};

const network = new vis.Network(container, data, options);

async function loadFrames() {
    const response = await fetch("replay_frames.json");
    frames = await response.json();

    requestAnimationFrame(replayStep);
}

function ensureNode(id) {
    if (!nodes.get(id)) {
        nodes.add({
            id: id,
            label: id.split("/").pop()
        });
    }
}

function replayStep() {
    if (playing && frameIndex < frames.length) {
        const frame = frames[frameIndex];

        ensureNode(frame.from);
        ensureNode(frame.to);

        edges.forEach(edge => {
    edges.update({
        id: edge.id,
        color: {
            color: "rgba(100,100,255,0.15)"
        }
    });
});

edges.add({
    from: frame.from,
    to: frame.to,
    color: {
        color: "#ff5555"
    },
    width: 3
});

        frameIndex++;
    }

    requestAnimationFrame(replayStep);
}

function toggleReplay() {
    playing = !playing;
}

loadFrames();
</script>

</body>
</html>
"""

        output.write_text(html, encoding="utf-8")
        return str(output)