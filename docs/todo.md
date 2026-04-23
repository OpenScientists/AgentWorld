# TODO

> Working document for the next implementation phase.
> This file is not a brainstorming note. It is a concrete build plan for parallel execution.

## 1. What We Are Building

We are building a **filesystem-native organization runtime for strong agents**.

The system should be able to instantiate an organization such as a lab, institute, school, or review board. Inside that organization, each node is a strong agent such as `Claude Code`, `Codex`, or `OpenClaw`, and collaboration happens through a structured workspace instead of a heavy in-memory message layer.

The point is not to wrap strong agents more tightly. The point is to give them a well-structured environment in which they can operate like members of a real institution:

- shared memory exists as files
- local memory exists as files
- short-term and long-term memory are separated
- handoffs and requests exist as durable artifacts
- graph execution remains available, but only as one coordination layer inside a larger platform

This means our next phase is not "add more protocol objects." It is "build the workspace, memory, and runtime conventions that let strong agents form a durable organization."

## 2. Core Ideas

### 2.1 The organization is the primary object

The top-level runtime unit should be an organization, not a single prompt call and not a single agent session. The system should know what units exist, what each agent is responsible for, what workspace each role owns, and how work moves across the organization.

### 2.2 The filesystem is the default collaboration layer

We should treat files and folders as the native interface for memory, communication, review, and recovery. Strong agents are already good at reading directories, discovering context, editing documents, and resuming from local state. The framework should lean into that ability instead of hiding everything behind custom protocol wrappers.

### 2.3 Memory must be layered and inspectable

We need explicit support for global memory, local memory, long-term memory, and short-term memory. These layers should be visible in the workspace and easy for both humans and agents to inspect. Hidden state should be minimized.

### 2.4 The runtime should stay thin

The runtime should create structure, preserve checkpoints, maintain indexes, and help schedule work. It should not become a giant abstraction wall. Strong agents should still be able to explore the workspace directly.

### 2.5 Skills belong to roles, not only to graphs

The repository already has a `skills/` space. In the organization model, skills should be attached to agents and roles through manifests, so each operator can load the right capabilities for its organizational function.

## 3. Fixed Implementation Map

To keep the work parallel, we should first freeze the target code layout. The modules below are the planned ownership boundaries for the next phase.

```text
docs/
├── todo.md
├── architecture.md
├── auto-research-use-case.md
├── autor-parity.md
└── organization-layout.md

src/agentworld/
├── apps/
│   ├── __init__.py
│   └── auto_research.py
├── approval/
│   ├── __init__.py
│   └── base.py
├── artifacts/
│   ├── __init__.py
│   ├── index.py
│   └── models.py
├── manifest/
│   ├── __init__.py
│   └── run.py
├── research/
│   ├── __init__.py
│   ├── evidence.py
│   ├── experiment.py
│   ├── hypothesis.py
│   └── writing.py
├── benchmarks/
│   ├── __init__.py
│   ├── catalog.py
│   ├── records.py
│   └── loaders.py
├── organization/
│   ├── __init__.py
│   ├── models.py
│   ├── loader.py
│   └── validation.py
├── workspace/
│   ├── __init__.py
│   ├── layout.py
│   ├── bootstrap.py
│   └── templates.py
├── memory/
│   ├── __init__.py
│   ├── models.py
│   ├── store.py
│   └── index.py
├── coordination/
│   ├── __init__.py
│   ├── models.py
│   └── store.py
├── recovery/
│   ├── __init__.py
│   ├── ledger.py
│   └── checkpoints.py
├── policy/
│   ├── __init__.py
│   ├── models.py
│   └── engine.py
├── operator/
│   ├── base.py
│   ├── models.py
│   └── filesystem.py
├── stage/
│   ├── __init__.py
│   ├── handoff.py
│   ├── markdown.py
│   ├── models.py
│   ├── operator.py
│   └── prompts.py
├── workflows/
│   ├── __init__.py
│   ├── auto_research.py
│   ├── knowledge.py
│   ├── reasoning.py
│   └── agentic.py
└── runtime/
    ├── __init__.py
    ├── executor.py
    ├── events.py
    └── organization.py

tests/
├── test_artifact_primitives.py
├── test_auto_research_app.py
├── test_auto_research_workflow.py
├── test_research_manifests.py
├── test_run_manifest.py
├── test_benchmark_catalog.py
├── test_benchmark_entrypoints.py
├── test_organization_models.py
├── test_workspace_bootstrap.py
├── test_memory_store.py
├── test_coordination_store.py
├── test_recovery_store.py
├── test_policy_engine.py
├── test_operator_filesystem.py
├── test_organization_runtime.py
├── test_workspace_primitives.py
└── test_workflow_templates.py

examples/
├── auto-research/
│   ├── README.md
│   └── run.py
├── organization_lab.py
├── organization_review_board.py
└── benchmarks/
    ├── run_sfe.py
    ├── run_sgi_deepresearch.py
    ├── run_researchclawbench.py
    └── run_scicode.py
```

The important constraint is simple: each work item below should mostly own one directory or one file group. That keeps the team parallel.

## 4. Auto-Research Use Case

AutoR should be treated as an upper-layer research application, not as a peer framework that AgentWorld copies directly.

AgentWorld should sit one layer lower as the Python package that provides the reusable building blocks for AutoR-style systems:

- filesystem-native run workspaces
- fixed-stage workflow contracts
- stage draft and final promotion
- approved cross-stage memory
- artifact requirements and indexing
- human or automated approval gates
- strong-agent operator backends

The reference use case lives under `examples/auto-research/`. It should demonstrate that an AutoR-like eight-stage research workflow can be expressed clearly on top of AgentWorld without vendoring or modifying AutoR.

The current parity map is maintained in `docs/autor-parity.md`. It should be updated whenever we move an AutoR capability from application policy into a reusable AgentWorld primitive.

## 5. Benchmark Workflow Program

These benchmarks are one of the main external targets for the framework.

The goal is not to build one-off scripts for each dataset. The goal is to use one common runtime to instantiate reusable workflow families that can cover:

- Stage 1 knowledge SFT tasks
- Stage 2 reasoning RL tasks
- Stage 3 agent tool-calling tasks

### 5.1 Target Benchmark Matrix

| Dataset | Training Stage | Priority | Discipline | Link | Task Type | Example Input | Example Output |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SFE | 1: Knowledge SFT | core | Scientific image understanding, currently astronomy examples | https://huggingface.co/datasets/InternScience/SFE | Multimodal | `Image: stellar spectrum; estimate [alpha/M]` | `0.12627530097961426` |
| Mol-Instructions | 1: Knowledge SFT | core | Chemistry, biology, molecules, and proteins | https://huggingface.co/datasets/zjunlp/Mol-Instructions | Text-only | `Please give me some details about this molecule: [C][C][C]...` | `The molecule is a 3-sn-phosphatidyl-L-serine ...` |
| MSEarth_MCQ | 1: Knowledge SFT | optional | Earth science | https://huggingface.co/datasets/PrismaX/MSEarth_MCQ | Multimodal | `Image + caption + question: Which aquifer shows the highest spread of the Fe-Mn hazard?` | `C. Aquifer 3` |
| SGI-DeepResearch | 2: Reasoning RL | core | Multidisciplinary scientific reasoning | https://huggingface.co/datasets/InternScience/SGI-DeepResearch | Text-only | `In GW150914's ridge points ... compute total mass M` | `62.0` |
| SGI-Reasoning | 2: Reasoning RL | core | Multidisciplinary multimodal scientific reasoning | https://huggingface.co/datasets/InternScience/SGI-Reasoning | Multimodal | `Image + question: SERS distance changes from 8.5 to 2.3; compute the similarity change` | `1 (answer index)` |
| TRQA | 2: Reasoning RL | core | Biomedicine and target discovery | https://huggingface.co/datasets/GENTEL-Lab/TRQA | Text-only | `Which cardiovascular complications are directly associated with FGF23 excess?` | `BCD` |
| hle | 2: Reasoning RL | optional | Frontier multidisciplinary science | https://huggingface.co/datasets/cais/hle | Multimodal | `What is the largest prime divisor of 8139881` | `5003` |
| Earth-Silver | 2: Reasoning RL | optional | Earth science and ecology | https://huggingface.co/datasets/ai-earth/Earth-Silver | Text-only | `How do varying fire regimes and browsing intensities influence vegetation dynamics ... ?` | `Varying fire regimes and browsing intensities serve as critical factors ...` |
| SGI-IdeaGeneration | 2: Reasoning RL | core | Multidisciplinary scientific idea generation | https://huggingface.co/datasets/InternScience/SGI-IdeaGeneration | Text-only | `Based on related work and the challenge, generate a novel and detailed research proposal` | `AlphaFold introduces an end-to-end deep learning architecture ...` |
| ResearchClawBench | 3: Agent Tool Calling | core | Multidisciplinary scientific research agent benchmark | GitHub: https://github.com/InternScience/ResearchClawBench<br>HF mirror: https://huggingface.co/datasets/InternScience/ResearchClawBench | Project-level | `Constrain ultralight bosons from black-hole posterior samples and produce a paper-level report` | `code + figures + report/report.md` |
| SciCode | 3: Agent Tool Calling | core | Scientific computing and code generation | https://huggingface.co/datasets/SciCode1/SciCode | Project-level | `Write a script to integrate the Berendsen thermostat and barostat ...` | `Python implementation that passes provided tests` |

### 5.2 Workflow Families We Need

We should cover the benchmark set through three reusable workflow families rather than through eleven unrelated pipelines.

**Knowledge workflows** should target Stage 1 datasets such as `SFE`, `Mol-Instructions`, and `MSEarth_MCQ`. These workflows should focus on structured prompting, skill selection, modality handling, and answer normalization for knowledge-heavy tasks.

**Reasoning workflows** should target Stage 2 datasets such as `SGI-DeepResearch`, `SGI-Reasoning`, `TRQA`, `hle`, `Earth-Silver`, and `SGI-IdeaGeneration`. These workflows should support multi-step reasoning, optional tool use, evidence gathering, intermediate scratchpads, and final answer extraction.

**Agentic project workflows** should target Stage 3 datasets such as `ResearchClawBench` and `SciCode`. These workflows should support project bootstrapping, filesystem-native memory, long-running execution, tool calling, code generation, artifact production, and final report assembly.

## 6. Parallel TODO

Tasks 1-6 are designed to run in parallel with minimal overlap. Tasks 7-8 are integration-facing and should start once the core file contracts are stable enough to import.

### 1. Freeze the organization schema

**Files:** `src/agentworld/organization/__init__.py`, `src/agentworld/organization/models.py`, `src/agentworld/organization/loader.py`, `src/agentworld/organization/validation.py`, `tests/test_organization_models.py`

Build the typed organization contract for the whole project. This task should define `OrganizationSpec`, `UnitSpec`, `AgentSpec`, `ProjectSpec`, `RoleSpec`, and the skill-binding fields each agent can declare. It should also support loading a manifest from disk and validating required fields. The output of this task is the stable data model that every other task can depend on without touching runtime logic.

### 2. Build the workspace layout and bootstrapper

**Files:** `src/agentworld/workspace/__init__.py`, `src/agentworld/workspace/layout.py`, `src/agentworld/workspace/bootstrap.py`, `src/agentworld/workspace/templates.py`, `tests/test_workspace_bootstrap.py`, `docs/organization-layout.md`

Build the code that materializes an organization onto the filesystem. This task should define the canonical directory tree, the default files each unit and agent should receive, and the bootstrap entrypoint that can create a runnable workspace from an organization spec. The result should be a generated organization root that humans and agents can both navigate immediately.

### 3. Build the layered memory module

**Files:** `src/agentworld/memory/__init__.py`, `src/agentworld/memory/models.py`, `src/agentworld/memory/store.py`, `src/agentworld/memory/index.py`, `tests/test_memory_store.py`

Build the file-native memory layer for global/local and long-term/short-term memory. This task should define the memory record model, file naming rules, write and read helpers, and lightweight indexes so agents can discover the right context quickly. The goal is to make memory visible, durable, and queryable without introducing a hidden database.

### 4. Build the coordination artifact store

**Files:** `src/agentworld/coordination/__init__.py`, `src/agentworld/coordination/models.py`, `src/agentworld/coordination/store.py`, `tests/test_coordination_store.py`

Build the durable file-based collaboration layer. This task should define how inbox items, handoffs, review requests, and decision records are represented on disk, including minimal metadata and lifecycle states. The goal is to replace vague "message passing" with concrete workspace artifacts that can be audited, resumed, and processed by any strong agent.

### 5. Build ledger and checkpoint persistence

**Files:** `src/agentworld/recovery/__init__.py`, `src/agentworld/recovery/ledger.py`, `src/agentworld/recovery/checkpoints.py`, `tests/test_recovery_store.py`

Build the append-only record and checkpoint layer for long-running organizations. This task should define ledger entries, checkpoint snapshots, storage rules, and reload helpers so we can reconstruct execution state from the workspace itself. The goal is to support pause, resume, inspection, and postmortem analysis without depending on transient process memory.

### 6. Build the visibility and permission engine

**Files:** `src/agentworld/policy/__init__.py`, `src/agentworld/policy/models.py`, `src/agentworld/policy/engine.py`, `tests/test_policy_engine.py`

Build the access model for organization workspaces. This task should define what an agent, unit, or role can read and write, how shared and private areas are marked, and what the default permission behavior should be. The result should be a lightweight policy layer that the runtime and operator adapters can consult without forcing provider-specific logic into every module.

### 7. Build the operator-side filesystem adapter

**Files:** `src/agentworld/operator/filesystem.py`, `src/agentworld/operator/models.py`, `tests/test_operator_filesystem.py`

Build the adapter that turns an organization workspace into operator-ready execution context. This task should map organization specs, memory paths, coordination artifacts, and mounted skills into a form that operators can pass to controllers. The main deliverable is not a new controller; it is a clean way to make the existing operator layer work against directory-native organizations.

### 8. Build the organization runtime bridge

**Files:** `src/agentworld/runtime/organization.py`, `src/agentworld/runtime/__init__.py`, `examples/organization_lab.py`, `examples/organization_review_board.py`, `tests/test_organization_runtime.py`

Build the thinnest runtime that can execute work over the organization workspace. This task should connect graph execution, workspace bootstrap output, operator filesystem context, and recovery helpers into one runnable flow. The result should be at least two end-to-end examples: one lab-style organization and one review-board organization, both using the filesystem-native layout rather than an in-memory toy setup.

### 9. Build the benchmark catalog and dataset contracts

**Files:** `src/agentworld/benchmarks/__init__.py`, `src/agentworld/benchmarks/catalog.py`, `src/agentworld/benchmarks/records.py`, `src/agentworld/benchmarks/loaders.py`, `tests/test_benchmark_catalog.py`

Build the benchmark registry for the target matrix above. This task should define a normalized record for every benchmark, including training stage, priority, modality, discipline, dataset link, expected answer shape, and example I/O contract. It should also provide lightweight dataset-loading hooks so workflows can consume benchmark items through one common interface instead of custom per-dataset glue.

### 10. Build reusable workflow templates for benchmark families

**Files:** `src/agentworld/workflows/__init__.py`, `src/agentworld/workflows/knowledge.py`, `src/agentworld/workflows/reasoning.py`, `src/agentworld/workflows/agentic.py`, `tests/test_workflow_templates.py`

Build three reusable workflow families for the benchmark program: one for knowledge SFT tasks, one for reasoning RL tasks, and one for agent tool-calling tasks. Each workflow template should define the minimal operator graph, required skills, memory surfaces, artifact expectations, and answer-finalization logic for its benchmark family. The goal is to make new benchmark coverage a configuration exercise rather than a brand-new system design each time.

### 11. Build benchmark entrypoints and reference runs

**Files:** `examples/benchmarks/run_sfe.py`, `examples/benchmarks/run_sgi_deepresearch.py`, `examples/benchmarks/run_researchclawbench.py`, `examples/benchmarks/run_scicode.py`, `tests/test_benchmark_entrypoints.py`

Build reference entrypoints that exercise the unified workflow stack on representative benchmarks from all three stages. These scripts should prove that the same platform can run a multimodal knowledge task, a scientific reasoning task, and a project-level agent benchmark without changing the underlying runtime model. The result should be a small but real benchmark-facing surface that the team can extend dataset by dataset.
