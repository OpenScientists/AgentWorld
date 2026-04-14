<a id="top"></a>

<div align="center">
  <h1>AgentWorld</h1>
</div>

<div align="center">

[![Official Site](https://img.shields.io/badge/Official%20Site-0f8b7b.svg?logo=homepage)](https://black-yt.github.io/AgentWorld/)
[![GitHub](https://img.shields.io/badge/GitHub-000000?logo=github&logoColor=white)](https://github.com/black-yt/AgentWorld)
[![CI](https://github.com/black-yt/AgentWorld/actions/workflows/ci.yml/badge.svg)](https://github.com/black-yt/AgentWorld/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Skills](https://img.shields.io/badge/Skills-5-green.svg)](#-skill-marketplace)
[![Operators](https://img.shields.io/badge/Operators-3-orange.svg)](#-supported-operators)
[![GitHub stars](https://img.shields.io/github/stars/black-yt/AgentWorld?style=social)](https://github.com/black-yt/AgentWorld)

**Building the open ecosystem platform for strong agents**

[Quick Start](#quick-start) | [Skill Marketplace](#skill-marketplace) | [How It Works](#how-it-works) | [Supported Operators](#supported-operators) | [Examples](#examples) | [Roadmap](#roadmap)

</div>

<p align="center">
  <img src="docs/assets/agentworld-vision-diagram.svg" alt="Strong-Agent Ecosystem Platform Vision" width="1100">
</p>

---

AgentWorld is the foundation repository for a broader **open ecosystem platform for strong agents**.

The long-term direction is larger than a graph runtime alone: it aims to provide a shared platform for **infrastructure**, **skills**, **benchmarks**, **applications**, and **community collaboration** around strong agents such as Claude Code, Codex, and OpenClaw.

This repository currently implements one core slice of that platform:

- provider-specific control through **controllers**
- uniform upper-layer execution through **operators**
- structured inter-agent communication through an explicit **A2A protocol**
- scheduling, checkpointing, and replay through a **graph runtime**
- reusable domain guidance through a repo-local **skill marketplace**

In other words, the graph runtime is an important implemented subsystem here, but it is not the full platform story.

## Overview

### ✨ Highlights

<table>
<tr>
<td align="center" width="25%">🌐<br/><b>Open Platform Direction</b><br/><sub>A broader ecosystem vision spanning infrastructure, skills, benchmarks, applications, and community growth</sub></td>
<td align="center" width="25%">🏗️<br/><b>Platform Foundation</b><br/><sub>This repository currently focuses on the controller, operator, protocol, runtime, and graph foundation layer</sub></td>
<td align="center" width="25%">🧩<br/><b>Skill Platform Seed</b><br/><sub>Skills can already be packaged and loaded per node, forming the base of a larger skill platform</sub></td>
<td align="center" width="25%">📦<br/><b>Recoverable Runtime</b><br/><sub>Checkpoints, traceability, artifacts, and resumable execution are treated as core runtime concerns</sub></td>
</tr>
<tr>
<td align="center">🔌<br/><b>Controller Boundary</b><br/><sub>Provider-specific session lifecycle, tool policy, and stream parsing stay isolated</sub></td>
<td align="center">📨<br/><b>Explicit A2A</b><br/><sub>Messages, tool results, handoffs, and artifacts are structured instead of prompt glue</sub></td>
<td align="center">🕸️<br/><b>Graph Runtime Slice</b><br/><sub>The graph layer is currently the most concrete orchestration subsystem, not the entire platform definition</sub></td>
<td align="center">🧪<br/><b>Real Smoke Path</b><br/><sub>Claude Code already runs through the runtime in a real graph-backed case with CI-backed repository tests</sub></td>
</tr>
</table>

### 💡 Why AgentWorld

Most older agent frameworks focus on what a model can call.

This platform direction starts from what a strong agent can actually **run**:

- a real session
- a working directory
- a permission model
- tool calls with side effects
- long-running stateful execution
- collaboration with other agents in the same system

That changes the architecture:

- a controller is not optional glue, it is the provider boundary
- an operator is not just a prompt wrapper, it is a durable execution unit
- a skill is not a marketing label, it is reusable execution guidance attached to an operator
- a graph runtime is necessary, but it must live inside a broader platform that also supports skills, benchmarks, applications, and ecosystem growth
- the runtime must own checkpoint, resume, interrupt, trace, and artifact flow

### 🧭 Platform Scope

| Layer | Role | Status in this repository |
| --- | --- | --- |
| **Platform Foundation** | controllers, operators, protocol, runtime, state, graph execution | **Current implementation focus** |
| **Skill Platform** | reusable skill packaging, loading, references, scripts, future exchange | **Early implementation** |
| **Benchmark + Evaluation** | benchmark tasks, scorecards, leaderboards, comparisons | **Planned** |
| **Application Platform** | auto-research, reliable agentic systems, agentic RL, domain workflows | **Planned / example-driven** |
| **Ecosystem Layer** | community contribution, collaboration, future marketplace dynamics | **Vision / planned** |

### 🆕 News

- **2026-04-13** Added a dedicated `skills/` marketplace with research-oriented skills for paper search, literature synthesis, citation audit, experiment planning, and result audit.
- **2026-04-13** Added explicit per-node `skills` support so each operator node can receive a different skill set through the runtime.
- **2026-04-13** Published the GitHub Pages site under `docs/` and split the long architecture note into a dedicated design document.
- **2026-04-13** Refined the public repository surface so README and site stay English-first while private notes remain local and ignored.

<a id="quick-start"></a>
## 🚀 Quick Start

Install the package:

```bash
python -m pip install -e .
```

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

Run the in-memory planner / coder / reviewer graph:

```bash
python examples/planner_coder_reviewer.py
```

Run the real Claude Code smoke graph:

```bash
python examples/claude_real_smoke.py
```

The Claude smoke case requires a working local `claude` CLI and an authenticated environment.

<a id="how-it-works"></a>
## ⚙️ How It Works

The diagram below describes the **current foundation layer implemented in this repository**. It is not intended to represent the entire future ecosystem platform.

```mermaid
flowchart TB
    U["User / App"]
    B["Graph Builder"]
    G["Compiled Graph"]
    R["Runtime"]

    subgraph AW["AgentWorld Core"]
        O["Operator Layer"]
        K["Skill Loader"]
        P["A2A Protocol"]
        S["State + Checkpoint + Trace"]
    end

    subgraph C["Controllers"]
        C1["ClaudeCodeController"]
        C2["CodexController"]
        C3["OpenClawController"]
    end

    subgraph A["Strong Agents"]
        A1["Claude Code"]
        A2["Codex"]
        A3["OpenClaw"]
    end

    U --> B --> G --> R
    R --> O
    O --> K
    O --> P
    R --> S
    O --> C1 --> A1
    O --> C2 --> A2
    O --> C3 --> A3
```

### Current Foundation Execution Flow

1. Build a graph of operator-backed nodes
2. Assign objective, role, tool policy, and skills to each node
3. Compile the graph into a runtime
4. Let the runtime assemble a normalized operator request
5. Let the controller drive the real strong agent
6. Convert events into messages, artifacts, handoffs, and state patches
7. Merge state, route the next nodes, and persist traceable execution state

### Current Foundation Boundaries

| Boundary | Responsibility |
| --- | --- |
| Controller | provider-specific invocation, sessions, stream parsing, tool policy mapping |
| Operator | uniform request/result contract, prompt assembly, skill loading, normalized outputs |
| Skill | reusable domain guidance, references, scripts, and task-specific workflow instructions |
| A2A Protocol | messages, tool outputs, handoffs, artifact references |
| Runtime | scheduling, state merge, checkpoint, resume, interrupt, trace |

<a id="skill-marketplace"></a>
## 🧩 Skill Marketplace

AgentWorld treats skills as reusable execution modules that can be attached to individual operator nodes.

A skill is stored as a folder, usually with:

- `SKILL.md` for instructions and activation guidance
- optional `references/` for domain notes
- optional `scripts/` for repeatable local tooling
- optional `assets/` for templates or helper files

### Included Research Skills

| Skill | Purpose |
| --- | --- |
| `research-paper-search` | find papers, databases, identifiers, and evidence trails before execution |
| `literature-synthesis` | turn a paper set into claims, themes, contradictions, and gaps |
| `citation-audit` | validate references, metadata, citation hygiene, and bibliography consistency |
| `experiment-planning` | design executable research plans, deliverables, risks, and validation steps |
| `result-audit` | review outputs for unsupported claims, missing evidence, weak baselines, and incomplete analysis |

### Load Different Skills Per Operator

```python
from agentworld import AgentGraph, DefaultOperator

graph = AgentGraph(name="research-flow")
graph.add_operator("planner", planner_operator)
graph.add_operator("reviewer", reviewer_operator)

graph.add_node(
    "plan",
    operator="planner",
    objective="Search relevant work and plan the study",
    skills=["research-paper-search", "literature-synthesis", "experiment-planning"],
)

graph.add_node(
    "review",
    operator="reviewer",
    objective="Audit claims and evidence",
    skills=["citation-audit", "result-audit"],
)
```

The runtime injects the selected skill list into the operator request, so different nodes can run with different domain guidance even when they use the same underlying controller.

### Add Your Own Skill

Create a new folder under `skills/`:

```text
skills/
└── my-skill/
    └── SKILL.md
```

Minimal `SKILL.md` format:

```md
---
name: my-skill
description: What this skill should be used for.
---

# My Skill

## When to Use This Skill
- ...

## Workflow
- ...
```

<a id="supported-operators"></a>
## 🤖 Supported Operators

The current platform foundation is designed to schedule strong agents through provider-specific controllers:

| Operator | Current State | Notes |
| --- | --- | --- |
| **Claude Code** | Implemented | Real CLI-backed controller with stream parsing and smoke coverage |
| **Codex** | Scaffolded | Contract is present, runtime path still needs full implementation |
| **OpenClaw** | Scaffolded | Contract is present, controller behavior still needs full implementation |

<a id="examples"></a>
## 🧪 Examples

### Planner -> Coder -> Reviewer

[examples/planner_coder_reviewer.py](examples/planner_coder_reviewer.py)

Validates:

- sequential graph execution
- reducer-based state merging
- artifact creation
- message propagation
- per-node skill injection

### Real Claude Code Graph

[examples/claude_real_smoke.py](examples/claude_real_smoke.py)

Validates:

- real `ClaudeCodeController` command assembly
- real event parsing from Claude Code
- `tool_call` and `tool_result` normalization
- planner-to-reviewer graph handoff

### Real Claude Code Skill Graph

[examples/claude_skill_smoke.py](examples/claude_skill_smoke.py)

Validates:

- repo-local skill loading
- skill content injection into the operator instruction
- real Claude Code execution without persistent Claude configuration changes
- skill-aware output generation

## 📁 Repository Structure

```text
.
├── README.md
├── docs/
│   ├── index.html
│   ├── architecture.md
│   └── assets/
├── examples/
├── skills/
│   ├── README.md
│   ├── research-paper-search/
│   ├── literature-synthesis/
│   ├── citation-audit/
│   ├── experiment-planning/
│   └── result-audit/
├── src/agentworld/
│   ├── controller/
│   ├── graph/
│   ├── operator/
│   ├── protocol/
│   └── runtime/
└── tests/
```

## 📚 Documentation

- Official site: [black-yt.github.io/AgentWorld](https://black-yt.github.io/AgentWorld/)
- Architecture note: [docs/architecture.md](docs/architecture.md)
- Skill marketplace: [skills/README.md](skills/README.md)

<a id="roadmap"></a>
## 🗺️ Roadmap

- complete the Codex controller
- complete the OpenClaw controller
- harden checkpoint, resume, and trace persistence
- extend graph routing and handoff semantics
- grow the skill platform with richer loading, references, and reusable execution assets
- add benchmark and evaluation primitives for strong-agent workflows
- publish stronger application-layer examples for research and domain-specific multi-agent systems
- expand the public platform docs and ecosystem-facing site

---

## Community

### 🤝 Contributing

Contributions are especially useful around:

- controller implementations
- runtime behavior
- graph semantics
- skill design
- tests and examples
- documentation improvements

### 📬 Contact

Open an issue for bugs, design questions, controller support requests, or skill contributions.

### ⭐ Star History

<a href="https://www.star-history.com/#black-yt/AgentWorld&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=black-yt/AgentWorld&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=black-yt/AgentWorld&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=black-yt/AgentWorld&type=Date" />
  </picture>
</a>

<p align="right"><a href="#top">🔝 Back to top</a></p>
