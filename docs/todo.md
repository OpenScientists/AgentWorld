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
└── organization-layout.md

src/agentworld/
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
└── runtime/
    ├── __init__.py
    ├── executor.py
    ├── events.py
    └── organization.py

tests/
├── test_organization_models.py
├── test_workspace_bootstrap.py
├── test_memory_store.py
├── test_coordination_store.py
├── test_recovery_store.py
├── test_policy_engine.py
├── test_operator_filesystem.py
└── test_organization_runtime.py

examples/
├── organization_lab.py
└── organization_review_board.py
```

The important constraint is simple: each work item below should mostly own one directory or one file group. That keeps the team parallel.

## 4. Parallel TODO

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
