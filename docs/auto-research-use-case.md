# Auto-Research Use Case

AgentWorld is not trying to replace AutoR as an application. It is the lower package layer that should make AutoR-class systems straightforward to build.

The intended relationship is:

```text
AutoR-style research application
    uses
AgentWorld Python package
    provides
controllers, operators, workspaces, manifests, stage contracts, approval gates,
artifact indexes, recovery primitives, and graph/runtime infrastructure
```

## What AgentWorld Must Preserve From AutoR

AutoR is valuable because it treats research automation as a durable workflow, not a prompt chain. The core package therefore has to preserve the real application constraints:

- a run is a filesystem object
- stage summaries have hard output contracts
- provider sessions survive refinement attempts
- approved stages become durable cross-stage memory
- artifacts are indexed and validated, not just mentioned in prose
- rollback, repair, and resume are runtime features
- research-specific manifests are generated as part of the run

## What Is Now In AgentWorld Core

The current AgentWorld core now exposes the primitives required to build this class of application:

- `RunWorkspace` for the durable run layout
- `RunManifest` and `StageManifestEntry` for stage-by-stage state
- `StageSpec`, `StageRunRequest`, `StageRunResult`, and `StageRepairRequest`
- `ControllerStageOperator` for provider-backed strong-agent execution
- `ApprovalGate` implementations for manual or validation-only review
- `ArtifactRequirement`, artifact indexing, and schema inference
- stage handoffs, approved memory rebuild, and prior decision-ledger context
- `write_hypothesis_manifest`, `write_experiment_manifest`, and writing-bundle context
- `AutoResearchWorkflow` and `agentworld.apps.auto_research`

## What Still Belongs At The Application Layer

AutoR also contains product-facing surfaces that should remain above the framework:

- a terminal UI
- a web studio
- notebook-style interaction
- paper/release packaging
- repository bootstrap and corpus bootstrap

Those are valid next applications on top of AgentWorld, but they should not be collapsed into the core runtime.

## Current Example

The current example uses a real Claude Code backed stage operator:

```bash
python examples/auto-research/run.py "Study whether filesystem-native strong-agent organizations improve recoverability in long research workflows."
```

The generated run now contains the same class of durable state AutoR depends on:

- `goal.md`
- `user_input.txt`
- `memory.md`
- `run_config.json`
- `run_manifest.json`
- `artifact_index.json`
- `logs.txt`
- `events.jsonl`
- `logs_raw/`
- `prompt_cache/`
- `operator_state/`
- `stages/`
- `handoffs/`
- `workspace/results/experiment_manifest.json`
- `workspace/notes/hypothesis_manifest.json`

Unit tests use deterministic scripted operators, but the example itself is backed by the real controller stack.
