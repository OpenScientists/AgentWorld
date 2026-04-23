# Auto-Research Example

This example shows how AgentWorld can express an AutoR-style research workflow as a use case.

AutoR is a concrete human-centered research application. AgentWorld sits below that layer: it provides reusable Python primitives for filesystem-native workspaces, stage contracts, artifact validation, approval gates, and operator-backed execution.

This example intentionally does not vendor or modify AutoR. It implements an AutoR-class workflow on top of AgentWorld core and runs it through a real strong-agent controller.

## Run

```bash
python examples/auto-research/run.py \
  --approval-mode validation-only \
  --permission-mode acceptEdits \
  --max-attempts 2 \
  "Build and evaluate a handwritten digit classification model on the scikit-learn digits dataset. Train at least two classical machine learning baselines, compare their accuracy and confusion matrices, save reusable Python code, produce one summary figure, and write a concise research-style report with methods, results, limitations, and reproducibility notes."
```

By default this uses Claude Code through `ClaudeCodeController`, so it requires:

- a working local `claude` CLI
- an authenticated Claude Code environment
- tool permissions sufficient to read, write, edit, and run local commands inside the run workspace

The CLI prints live progress while the strong agent is running:

- run root and selected stages
- stage start and attempt mode
- Claude session start
- tool calls and tool results
- assistant text excerpts
- validation, repair, review, approval, and failure status

Use `--quiet` to suppress progress lines and only print the final JSON result.

The generated run is written under:

```text
examples/auto-research/runs/
```

## What It Demonstrates

- A durable run directory
- Eight research stages
- Per-stage run manifest state
- Stage draft and final files
- Approved stage memory and handoffs
- Artifact requirements
- Artifact indexing with schema inference
- Hypothesis and experiment manifests
- Repair, rollback-ready state, and resumable provider sessions
- Human approval at stage boundaries
- Real strong-agent execution through AgentWorld's controller/operator layer

For non-interactive validation runs, use:

```bash
python examples/auto-research/run.py --approval-mode validation-only "Build a compact handwritten digit classifier evaluation report on the scikit-learn digits dataset."
```

That mode still uses the real controller. It only replaces the manual approval prompt with validation-based approval.

To continue a failed or interrupted run, point `--resume-run` at the run root:

```bash
python examples/auto-research/run.py \
  --resume-run examples/auto-research/runs/<run-id> \
  --approval-mode validation-only \
  --permission-mode acceptEdits \
  --max-attempts 2
```
