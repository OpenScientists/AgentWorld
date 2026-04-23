# Auto-Research Example

This example shows how AgentWorld can express an AutoR-style research workflow as a use case.

AutoR is a concrete human-centered research application. AgentWorld sits below that layer: it provides reusable Python primitives for filesystem-native workspaces, stage contracts, artifact validation, approval gates, and operator-backed execution.

This example intentionally does not vendor or modify AutoR. It implements an AutoR-class workflow on top of AgentWorld core and runs it through a real strong-agent controller.

## Run

```bash
python examples/auto-research/run.py \
  --runs-dir /tmp/agentworld-auto-research-runs \
  --approval-mode validation-only \
  --permission-mode bypassPermissions \
  --max-attempts 2 \
  --timeout 7200 \
  "Build and evaluate a handwritten digit classification model on the scikit-learn digits dataset. Train SVM-RBF, RandomForest, kNN, LogisticRegression, and DecisionTree baselines. The experiment stage must actually execute the Python training script and produce real cross-validation results, held-out test results, confusion matrices, hypothesis verdicts, figures, and a paper-style report. Do not use predicted or literature-only results as a substitute for execution."
```

By default this uses Claude Code through `ClaudeCodeController`, so it requires:

- a working local `claude` CLI
- an authenticated Claude Code environment
- tool permissions sufficient to read, write, edit, and run local commands inside the run workspace

`bypassPermissions` is recommended for this case because the experiment stage must execute Python training code. If the local Claude Code policy blocks Python execution, AgentWorld rejects the stage instead of allowing a prediction-only report.

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
/tmp/agentworld-auto-research-runs/
```

Validate the latest run:

```bash
RUN_ROOT="$(ls -td /tmp/agentworld-auto-research-runs/* | head -1)"

python - <<PY
import json
from pathlib import Path

root = Path("$RUN_ROOT")
manifest = json.loads((root / "run_manifest.json").read_text())
results = json.loads((root / "workspace/results/results.json").read_text())
required = [
    "workspace/results/cv_results.json",
    "workspace/results/test_results.json",
    "workspace/results/ablation_results.json",
    "workspace/results/hypothesis_verdicts.json",
    "workspace/results/confusion_matrices.npz",
    "workspace/figures/accuracy_comparison.png",
    "workspace/figures/confusion_matrices.png",
    "workspace/figures/summary.svg",
    "workspace/artifacts/paper.pdf",
]
missing = [path for path in required if not (root / path).exists()]
approved = sum(1 for stage in manifest["stages"] if stage["approved"])
print("run_root:", root)
print("run_status:", manifest["run_status"])
print("approved:", approved, "/", len(manifest["stages"]))
print("exit_code:", results.get("exit_code"))
print("missing:", missing or "none")
if manifest["run_status"] != "completed" or approved != len(manifest["stages"]):
    raise SystemExit("Run did not complete cleanly.")
if results.get("execution_blocker") or results.get("experiments_executed") is False:
    raise SystemExit("Experiment was blocked or not executed.")
if missing:
    raise SystemExit("Required artifacts are missing.")
PY
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
  --resume-run /tmp/agentworld-auto-research-runs/<run-id> \
  --approval-mode validation-only \
  --permission-mode bypassPermissions \
  --max-attempts 2
```
