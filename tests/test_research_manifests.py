from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agentworld.research import (
    format_experiment_manifest_for_prompt,
    format_hypothesis_manifest_for_prompt,
    validate_experiment_manifest,
    write_experiment_manifest,
    write_hypothesis_manifest,
)
from agentworld.workspace import create_run_workspace, write_text


STAGE_02_MARKDOWN = """# Stage 02: Hypothesis Generation

## Objective
Generate typed claims.

## Previously Approved Stage Summaries
_None yet._

## What I Did
Derived hypotheses from the literature.

## Key Results
### Theoretical Propositions
- **T1**: Better retrieval improves context quality.
  - Derived from: Literature synthesis.

### Empirical Hypotheses
- **H1**: Retrieval improves accuracy by at least 2 points.
  - Depends on: Retrieval pipeline.
  - Verification: Controlled ablation.

### Paper Claims (Provisional)
- **C1**: Retrieval improves robustness.
  - Status: provisional

## Files Produced
- `workspace/notes/hypotheses.md` - hypothesis notes

## Decision Ledger
- **Open Questions**: Which ablations matter most?
- **Locked Decisions**: Use typed hypotheses.
- **Assumptions**: Retrieval is feasible.
- **Rejected Alternatives**: Pure narrative claims.

## Suggestions for Refinement
1. Tighten measurement.
2. Expand controls.
3. Add failure cases.

## Your Options
1. Use suggestion 1
2. Use suggestion 2
3. Use suggestion 3
4. Refine with your own feedback
5. Approve and continue
6. Abort
"""


class ResearchManifestTests(unittest.TestCase):
    def test_write_hypothesis_manifest_parses_typed_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = create_run_workspace(runs_dir=Path(tmp), run_id="hypothesis", goal="test")
            manifest = write_hypothesis_manifest(workspace, STAGE_02_MARKDOWN)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            self.assertEqual(manifest.theoretical_propositions[0].identifier, "T1")
            self.assertIn("Empirical Hypotheses", format_hypothesis_manifest_for_prompt(manifest))

    def test_write_experiment_manifest_collects_schema_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = create_run_workspace(runs_dir=Path(tmp), run_id="experiment", goal="test")
            write_text(workspace.results_dir / "scores.csv", "setting,score\nbase,0.81\nabl,0.77\n")
            write_text(workspace.code_dir / "train.py", "print('ok')\n")
            write_text(workspace.notes_dir / "run.md", "# Run\n\nnotes\n")

            manifest = write_experiment_manifest(workspace)

            self.assertTrue(manifest.ready_for_analysis)
            self.assertEqual(manifest.summary["result_artifact_count"], 1)
            self.assertEqual(validate_experiment_manifest(workspace.experiment_manifest), [])

            payload = json.loads(workspace.experiment_manifest.read_text(encoding="utf-8"))
            schema = payload["result_artifacts"][0]["schema"]
            self.assertEqual(schema["kind"], "table")
            self.assertEqual(schema["row_count"], 2)
            self.assertIn("Result Artifacts", format_experiment_manifest_for_prompt(manifest))


if __name__ == "__main__":
    unittest.main()
