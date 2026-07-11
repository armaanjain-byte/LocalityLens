# LocalityLens

<p align="center">
  <img src="https://img.shields.io/badge/status-active-success" alt="status" />
  <img src="https://img.shields.io/badge/python-3.11+-blue" alt="python" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license" />
</p>

<p align="center">
  AST-aware observability for coding agents.
</p>

<p align="center">
  LocalityLens analyzes coding-agent execution traces to surface semantic thrashing, retrieval churn, context instability, and repository-scale locality failures.
</p>

**Live Dashboard →** [armaanjain-byte.github.io/localitylens](https://armaanjain-byte.github.io/LocalityLens/)

---


LocalityLens Dashboard
<img width="1920" height="1200" alt="Screenshot 2026-05-24 141908" src="https://github.com/user-attachments/assets/3b9069a9-3411-4776-a57b-eca18be733b0" />

---

## The Problem
Most coding agent tooling answers one question: *did the agent complete the task?*

Nobody is asking the adjacent question: *how inefficiently did the agent navigate the repository to get there?*

Agents repeatedly reload files, lose semantic context, re-retrieve symbols they already held, and fragment their working context across long-horizon tasks. This behavior is observable. It is not being observed.

LocalityLens fills that gap.

---

## What It Does

LocalityLens ingests execution traces from Claude Code, Cursor, or OpenHands, maps repository structure using AST analysis, and computes locality-oriented observability metrics.

The goal is behavioral analysis — not generation quality, not task scoring.

---

## Core Metrics

| Metric | Name | What It Measures |
|---|---|---|
| **LHR** | Locality Hit Rate | Fraction of required symbols already active in context at time of access |
| **STR** | Semantic Thrashing Rate | Frequency of reload → evict → reload cycles on the same symbol |
| **RRR** | Retrieval Redundancy Ratio | Repeated retrieval volume as a fraction of total retrievals |
| **CSS** | Context Stability Score | Semantic stability of the agent's active context over time |

High STR + low LHR = the agent is burning context budget revisiting code it already read.

---

## System Architecture

```
Execution Trace (Claude Code / Cursor / OpenHands)
    ↓
Trace Parser
    ↓
AST / Semantic Mapper  ←── Tree-sitter, symbol extraction, import graph
    ↓
Context Tracker        ←── tracks active symbol set per step
    ↓
Thrashing Engine       ←── detects reload/evict/reload cycles
    ↓
Metrics Engine         ←── computes LHR, STR, RRR, CSS
    ↓
Visualization Layer    ←── dashboard, transition graph, replay viewer
```

---

## Dashboard Features

<!-- Transition graph placeholder -->
![Transition Graph](docs/transition_graph.png)

- **Metrics overview** — LHR, STR, RRR, CSS with trend lines
- **Transition graph** — file-level navigation patterns across the execution
- **Replay viewer** — step-by-step trace playback with semantic state
- **Anomaly explorer** — flagged high-thrashing intervals
- **Retrieval churn visualization** — redundant access heatmap
- **Repository hotspot analysis** — most-revisited modules

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+ |
| AST Parsing | Tree-sitter |
| Graph Analysis | NetworkX |
| Data Processing | Pandas |
| Visualization | Plotly / HTML |
| CLI | Typer |
| Storage | SQLite + JSON |
| CI/CD | GitHub Actions |

---

## Installation

```bash
git clone https://github.com/armaanjain-byte/localitylens.git
cd localitylens

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## Usage

### Analyze a Trace

```bash
python analyze.py normalized_trace.json
```

### Output

```
index.html           # full interactive dashboard
metrics.json         # raw metric values
```

Or view the live deployment: [armaanjain-byte.github.io/localitylens](https://armaanjain-byte.github.io/localitylens/)

---

## Repository Structure

```
localitylens/
│
├── analysis/          # trace analysis pipelines
├── cli/               # Typer CLI
├── parser/            # trace parsers (Claude Code, Cursor, OpenHands)
├── semantic/          # AST mapping, symbol extraction, import graphs
├── metrics/           # LHR, STR, RRR, CSS computation
├── visualization/     # dashboard generation
├── tests/             # unit + integration tests
├── docs/              # screenshots, architecture diagrams
│
├── analyze.py
├── pyproject.toml
└── README.md
```

---

## Why Not Vectors, Why Not LLMs

LocalityLens intentionally avoids:

- vector databases
- embedding-based retrieval
- LLM serving
- orchestration frameworks

The analysis is deterministic. Metrics are computed from trace structure and AST-derived repository graphs — not from model inference. Reproducibility matters for evaluation tooling.

---

## Design Principles

**Reproducibility over convenience.** Analysis runs on any machine with the trace file and the repo. No cloud dependencies.

**Structural over semantic.** Context tracking uses AST-derived symbol graphs, not embedding similarity. The metrics measure observable behavior, not inferred intent.

**Metrics over dashboards.** The visualization is output, not the product. The product is `metrics.json` — a structured, comparable artifact.

---

## Use Cases

**Agent evaluation** — compare Claude Code vs OpenHands on locality efficiency across a shared benchmark task set.

**Debugging agent loops** — diagnose why an agent is looping on a module by inspecting STR spikes in the replay viewer.

**Context-window optimization research** — measure how retrieval redundancy scales with task length and repository size.

---

## Roadmap

- [ ] Multi-agent comparison (run two agents on the same task, compare metrics)
- [ ] SWE-bench trajectory integration
- [ ] Benchmark suite with reproducible task definitions
- [ ] Longitudinal trace analysis across agent versions
- [ ] Export pipeline for metric datasets

---

## Author

**Armaan Jain** · [github.com/armaanjain-byte](https://github.com/armaanjain-byte)

---

## License

MIT
