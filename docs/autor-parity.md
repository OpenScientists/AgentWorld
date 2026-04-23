# AutoR Parity Map

This note treats [AutoR](https://github.com/AutoX-AI-Labs/AutoR) as an upper-layer research application contract and checks whether AgentWorld now exposes the lower-level mechanisms needed to build it without simplification.

Analysis target: AutoR `main` at `621e7be` (`Fix Claude session resume recovery`).

The goal is not to clone AutoR into AgentWorld. The goal is to make sure AutoR-class systems can be implemented cleanly on top of AgentWorld core.

## Design Principle

AutoR mixes three layers:

1. provider-backed agent execution
2. durable workflow runtime
3. research-specific application policy

AgentWorld should own layers 1 and 2 directly, plus the reusable pieces of layer 3 that are still generic enough to belong in a framework.

## Parity Table

| AutoR design surface | AgentWorld mapping | Status |
| --- | --- | --- |
| durable run directory | `workspace.RunWorkspace` | Implemented |
| run manifest with per-stage state | `manifest.RunManifest`, `StageManifestEntry` | Implemented |
| stage draft and final files | `RunWorkspace.stage_draft_path`, `stage_final_path` | Implemented |
| stage attempt state and session continuity | `operator_state/`, `stage_session_file`, `ControllerStageOperator` | Implemented |
| fixed stage contracts | `stage.StageSpec`, `required_stage_template` | Implemented |
| stage markdown validation | `stage.validate_stage_markdown` | Implemented |
| fixed review options and refinement structure | `stage.FIXED_STAGE_OPTIONS` | Implemented |
| repair after invalid or missing draft | `StageRepairRequest`, `ControllerStageOperator.repair_stage_summary` | Implemented |
| approved cross-stage memory | `stage.append_approved_stage_summary`, `rebuild_memory_from_manifest` | Implemented |
| stage handoff summaries | `stage.write_stage_handoff`, `build_handoff_context` | Implemented |
| prior decision ledger context | `stage.build_decision_ledger_context` | Implemented |
| artifact requirements | `artifacts.ArtifactRequirement` | Implemented |
| artifact index with schema inference | `artifacts.write_artifact_index`, `format_artifact_index_for_prompt` | Implemented |
| literature evidence ledger validation | `research.validate_literature_evidence` | Implemented |
| hypothesis manifest | `research.write_hypothesis_manifest` | Implemented |
| experiment manifest | `research.write_experiment_manifest` | Implemented |
| writing bundle context | `research.build_writing_manifest` | Implemented |
| human approval gate | `approval.TerminalApprovalGate` | Implemented |
| automated validation-only gate | `approval.AutoApproveGate` | Implemented |
| rollback to earlier stage | `manifest.rollback_to_stage` | Implemented |
| resume from existing run root | `AutoResearchWorkflow.resume(...)` | Implemented |
| provider-backed strong-agent operator | `stage.ControllerStageOperator` + controllers | Implemented |
| AutoR-style app factory | `apps.auto_research.create_auto_research_app` | Implemented |

## What Stays Above the Framework

These parts are still application surfaces rather than framework primitives:

- terminal UI polish
- web studio / notebook surfaces
- paper package generation
- release package generation
- project bootstrap from an existing repository
- paper-corpus bootstrap and researcher profile extraction

These are not missing because the core is too weak. They are separate products that can now be built on top of the existing core contracts.

## Current Auto-Research Run Layout

An `examples/auto-research` run now materializes the same class of durable state that AutoR relies on:

```text
run_root/
├── goal.md
├── user_input.txt
├── memory.md
├── run_config.json
├── run_manifest.json
├── artifact_index.json
├── logs.txt
├── events.jsonl
├── logs_raw/
├── prompt_cache/
├── operator_state/
├── stages/
├── handoffs/
└── workspace/
    ├── literature/
    ├── code/
    ├── data/
    ├── results/
    │   └── experiment_manifest.json
    ├── figures/
    ├── writing/
    ├── notes/
    │   └── hypothesis_manifest.json
    ├── reviews/
    ├── artifacts/
    ├── bootstrap/
    └── profile/
```

## Why This Matters

The old simplified version of the auto-research example only proved that AgentWorld could loop over eight stages.

The current version proves something stronger:

- stage execution is stateful and resumable
- stage approval is explicit
- structured artifacts are regenerated and validated during the workflow
- approved knowledge is promoted into durable cross-stage memory
- rollback invalidates downstream work instead of silently ignoring it
- repair is part of the runtime contract, not an afterthought

That is the boundary we need if AgentWorld is going to sit underneath AutoR-class systems instead of being another demo workflow package.
