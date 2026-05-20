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
  LocalityLens analyzes coding-agent execution traces to detect semantic thrashing, retrieval churn, context instability, and repository-scale locality failures.
</p>

---

## Live Demo

Live dashboard:

[https://armaanjain-byte.github.io/localitylens/](https://armaanjain-byte.github.io/localitylens/)

---

## Overview

Modern coding agents repeatedly reload files, lose semantic locality, and waste context windows while navigating large repositories.

LocalityLens provides visibility into those failures.

The system ingests execution traces from coding agents such as Claude Code, Cursor, and OpenHands, maps repository structure using AST analysis, and computes locality-oriented observability metrics.

The goal is not code generation.

The goal is understanding how coding agents behave across repository-scale workflows.

---

## Core Capabilities

### Trace Analysis

Analyze coding-agent execution traces:

* Claude Code traces
* Cursor traces
* OpenHands traces
* Generic JSON traces

### Semantic Mapping

Repository-aware analysis using:

* Tree-sitter AST parsing
* symbol extraction
* import graph analysis
* semantic dependency tracking

### Locality Metrics

Compute:

| Metric | Description                                                                  |
| ------ | ---------------------------------------------------------------------------- |
| LHR    | Locality Hit Rate — percentage of required symbols already active in context |
| STR    | Semantic Thrashing Rate — reload → evict → reload frequency                  |
| RRR    | Retrieval Redundancy Ratio — repeated retrieval volume vs total retrieval    |
| CSS    | Context Stability Score — stability of semantic context over time            |

### Interactive Visualization

The dashboard includes:

* metrics overview
* transition graph
* replay viewer
* anomaly tracking
* repository interaction flow
* retrieval churn visualization
* hotspot analysis

---

## Why LocalityLens Exists

Most tooling for coding agents focuses on:

* prompting
* retrieval
* generation quality
* benchmark scoring

Very little tooling exists for understanding:

* semantic locality collapse
* repository navigation inefficiency
* repeated retrieval behavior
* context fragmentation
* long-horizon execution instability

LocalityLens focuses specifically on temporal semantic locality analysis for coding agents.

---

## System Architecture

```text
Trace Parser
    ↓
AST / Semantic Mapper
    ↓
Context Tracker
    ↓
Thrashing Engine
    ↓
Metrics Engine
    ↓
Visualization Layer
```

---

## Dashboard

The GitHub Pages deployment hosts the generated analysis dashboard directly.

Features currently integrated into the dashboard:

* replay visualization
* transition graph
* anomaly explorer
* semantic churn analysis
* trace playback
* metric summaries
* repository interaction tracking

---

## Example Workflow

### Input

```text
normalized_trace.json
repository path
```

### Run Analysis

```bash
python analyze.py normalized_trace.json
```

### Output

Generated outputs include:

```text
index.html
metrics.json
transition graph
replay visualization
```

---

## Example Use Cases

### Agent Observability

Understand:

* why agents repeatedly reopen files
* where context locality collapses
* which modules cause retrieval churn
* how repository navigation evolves over time

### Benchmark Evaluation

Compare coding agents on:

* locality efficiency
* retrieval redundancy
* context stability
* semantic reuse

### Research

Useful for:

* AI agent observability research
* repository-scale agent evaluation
* context-window optimization studies
* semantic memory analysis

---

## Technology Stack

| Layer           | Technology    |
| --------------- | ------------- |
| Backend         | Python        |
| AST Parsing     | Tree-sitter   |
| Graph Analysis  | networkx      |
| Data Processing | pandas        |
| Visualization   | Plotly / HTML |
| CLI             | Typer         |
| Storage         | JSON / SQLite |

---

## Repository Structure

```text
localitylens/
│
├── analysis/
├── cli/
├── parser/
├── semantic/
├── metrics/
├── visualization/
├── tests/
├── docs/
│
├── analyze.py
├── README.md
└── pyproject.toml
```

---

## Installation

### Clone Repository

```bash
git clone https://github.com/armaanjain-byte/localitylens.git
cd localitylens
```

### Create Environment

```bash
python -m venv venv
```

### Activate Environment

Windows:

```bash
venv\Scripts\activate
```

Linux / macOS:

```bash
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Project

### Analyze a Trace

```bash
python analyze.py normalized_trace.json
```

### Open Dashboard

Open generated:

```text
index.html
```

or view the live deployment:

[https://armaanjain-byte.github.io/localitylens/](https://armaanjain-byte.github.io/localitylens/)

---

## Development Goals

### Current Focus

* repository-scale observability
* semantic locality analysis
* retrieval churn tracking
* coding-agent workflow analysis

### Explicit Non-Goals

The project intentionally avoids:

* vector databases
* LLM serving
* autonomous agents
* orchestration frameworks
* prompt engineering systems
* cloud infrastructure complexity

---

## Performance Direction

Target capabilities:

* large trace processing
* repository-scale semantic mapping
* lightweight analysis pipeline
* reproducible metric computation

---

## Future Work

Planned extensions:

* multi-agent comparison
* benchmark suites
* longitudinal trace analysis
* additional parser integrations
* expanded semantic graph analytics
* export pipelines

---

## Research Direction

LocalityLens explores a broader question:

> Can coding-agent behavior be analyzed through semantic locality rather than only task completion?

The project treats repository interaction patterns as an observability problem rather than a pure generation problem.

---

## Author

Armaan Jain

GitHub:

[https://github.com/armaanjain-byte](https://github.com/armaanjain-byte)

---

## License

MIT License
