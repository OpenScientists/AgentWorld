from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentworld.manifest import (
    ensure_run_manifest,
    mark_stage_approved_manifest,
    mark_stage_review_manifest,
    mark_stage_running_manifest,
    rollback_to_stage,
)
from agentworld.workflows import AUTO_RESEARCH_STAGES
from agentworld.workspace import create_run_workspace


class RunManifestTests(unittest.TestCase):
    def test_manifest_initialization_and_stage_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = create_run_workspace(runs_dir=Path(tmp), run_id="manifest", goal="test")
            manifest = ensure_run_manifest(workspace, AUTO_RESEARCH_STAGES)

            self.assertEqual(manifest.run_status, "pending")
            self.assertEqual(len(manifest.stages), len(AUTO_RESEARCH_STAGES))

            stage = AUTO_RESEARCH_STAGES[0]
            running = mark_stage_running_manifest(workspace, AUTO_RESEARCH_STAGES, stage, attempt_no=1)
            self.assertEqual(running.run_status, "running")

            review = mark_stage_review_manifest(
                workspace,
                AUTO_RESEARCH_STAGES,
                stage,
                attempt_no=1,
                artifact_paths=("workspace/literature/survey.md",),
            )
            entry = next(item for item in review.stages if item.slug == stage.slug)
            self.assertEqual(entry.status, "human_review")

            approved = mark_stage_approved_manifest(
                workspace,
                AUTO_RESEARCH_STAGES,
                stage,
                attempt_no=1,
                artifact_paths=("workspace/literature/survey.md",),
            )
            entry = next(item for item in approved.stages if item.slug == stage.slug)
            self.assertTrue(entry.approved)
            self.assertEqual(entry.status, "approved")

    def test_rollback_marks_target_dirty_and_downstream_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = create_run_workspace(runs_dir=Path(tmp), run_id="rollback", goal="test")
            stage1, stage2, stage3 = AUTO_RESEARCH_STAGES[:3]

            mark_stage_approved_manifest(
                workspace,
                AUTO_RESEARCH_STAGES,
                stage1,
                attempt_no=1,
                artifact_paths=("workspace/literature/survey.md",),
            )
            mark_stage_approved_manifest(
                workspace,
                AUTO_RESEARCH_STAGES,
                stage2,
                attempt_no=1,
                artifact_paths=("workspace/notes/hypotheses.md",),
            )
            mark_stage_review_manifest(
                workspace,
                AUTO_RESEARCH_STAGES,
                stage3,
                attempt_no=1,
                artifact_paths=("workspace/data/study_design.json",),
            )

            rolled = rollback_to_stage(workspace, AUTO_RESEARCH_STAGES, stage2, reason="Need to revisit hypotheses.")
            stage2_entry = next(item for item in rolled.stages if item.slug == stage2.slug)
            stage3_entry = next(item for item in rolled.stages if item.slug == stage3.slug)

            self.assertEqual(stage2_entry.status, "pending")
            self.assertTrue(stage2_entry.dirty)
            self.assertEqual(stage3_entry.status, "stale")
            self.assertTrue(stage3_entry.stale)


if __name__ == "__main__":
    unittest.main()
