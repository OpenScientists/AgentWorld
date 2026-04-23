from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agentworld.stage import StageRepairRequest, StageRunRequest, StageRunResult
from agentworld.workflows import AutoResearchWorkflow
from agentworld.workspace import read_text, write_text


class ScriptedStageOperator:
    def __init__(self) -> None:
        self.invocations: dict[str, int] = {}

    def run_stage(self, request: StageRunRequest) -> StageRunResult:
        stage = request.stage
        workspace = request.workspace
        self.invocations[stage.slug] = self.invocations.get(stage.slug, 0) + 1
        files = self._materialize_stage_files(stage.slug, workspace)
        stage_file = workspace.stage_draft_path(stage.slug)
        write_text(stage_file, self._stage_markdown(stage, files))
        return StageRunResult(success=True, stage_file_path=stage_file, session_ref=f"session-{stage.slug}")

    def repair_stage_summary(self, request: StageRepairRequest) -> StageRunResult:
        return self.run_stage(
            StageRunRequest(
                stage=request.stage,
                prompt=request.original_prompt,
                workspace=request.workspace,
                attempt=request.attempt,
                continue_session=True,
            )
        )

    def _materialize_stage_files(self, slug: str, workspace) -> list[str]:
        if slug == "01_literature_survey":
            write_text(workspace.literature_dir / "survey.md", "# Survey\n\nStructured review.\n")
            write_text(
                workspace.literature_dir / "sources.json",
                json.dumps(
                    {
                        "sources": [
                            {"source_id": "S1", "title": "Paper One"},
                            {"source_id": "S2", "title": "Paper Two"},
                        ]
                    },
                    indent=2,
                    ensure_ascii=True,
                ),
            )
            write_text(
                workspace.literature_dir / "claims.json",
                json.dumps(
                    {
                        "claims": [
                            {"claim_id": "C1", "statement": "Signal strength improves.", "source_ids": ["S1"]},
                            {"claim_id": "C2", "statement": "Ablation matters.", "source_ids": ["S1", "S2"]},
                        ]
                    },
                    indent=2,
                    ensure_ascii=True,
                ),
            )
            return [
                "workspace/literature/survey.md",
                "workspace/literature/sources.json",
                "workspace/literature/claims.json",
            ]
        if slug == "02_hypothesis_generation":
            write_text(workspace.notes_dir / "hypotheses.md", "# Hypotheses\n\nTyped claim inventory.\n")
            return ["workspace/notes/hypotheses.md"]
        if slug == "03_study_design":
            write_text(workspace.notes_dir / "study_design.md", "# Design\n\nControlled protocol.\n")
            write_text(
                workspace.data_dir / "study_design.json",
                json.dumps({"dataset": "bench-a", "metrics": ["acc", "cost"]}, indent=2, ensure_ascii=True),
            )
            return ["workspace/notes/study_design.md", "workspace/data/study_design.json"]
        if slug == "04_implementation":
            write_text(workspace.code_dir / "implementation.py", "def run():\n    return {'ok': True}\n")
            write_text(
                workspace.data_dir / "config.json",
                json.dumps({"seed": 7, "batch_size": 8}, indent=2, ensure_ascii=True),
            )
            return ["workspace/code/implementation.py", "workspace/data/config.json"]
        if slug == "05_experimentation":
            write_text(
                workspace.results_dir / "results.json",
                json.dumps(
                    {
                        "experiments_executed": True,
                        "execution_status": "completed",
                        "model_results": [
                            {"setting": "base", "score": 0.81},
                            {"setting": "ablation", "score": 0.77},
                        ],
                    },
                    indent=2,
                    ensure_ascii=True,
                ),
            )
            return ["workspace/results/results.json"]
        if slug == "06_analysis":
            write_text(workspace.results_dir / "analysis.md", "# Analysis\n\nBase beats ablation.\n")
            write_text(
                workspace.figures_dir / "summary.svg",
                "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='120'><text x='10' y='60'>summary</text></svg>",
            )
            return ["workspace/results/analysis.md", "workspace/figures/summary.svg"]
        if slug == "07_writing":
            write_text(
                workspace.writing_dir / "main.tex",
                "\\documentclass{article}\n\\begin{document}\nResult.\n\\end{document}\n",
            )
            write_text(workspace.writing_dir / "references.bib", "@article{smith2024,title={A Study}}\n")
            write_text(workspace.artifacts_dir / "build_log.txt", "Final status: SUCCESS\n")
            write_text(
                workspace.artifacts_dir / "citation_verification.json",
                json.dumps(
                    {
                        "overall_status": "ok",
                        "total_citations": 2,
                        "claim_coverage": [{"claim": "Base beats ablation.", "source_ids": ["S1"]}],
                    },
                    indent=2,
                    ensure_ascii=True,
                ),
            )
            write_text(
                workspace.artifacts_dir / "self_review.json",
                json.dumps({"status": "pass", "checks": ["citations", "figures"]}, indent=2, ensure_ascii=True),
            )
            write_text(workspace.artifacts_dir / "paper.pdf", "%PDF-1.4\n% scripted test manuscript\n")
            return [
                "workspace/writing/main.tex",
                "workspace/writing/references.bib",
                "workspace/artifacts/build_log.txt",
                "workspace/artifacts/citation_verification.json",
                "workspace/artifacts/self_review.json",
                "workspace/artifacts/paper.pdf",
            ]
        if slug == "08_dissemination":
            write_text(workspace.reviews_dir / "readiness.md", "# Readiness\n\nReady.\n")
            write_text(workspace.artifacts_dir / "release_note.md", "# Release Note\n\nReady to ship.\n")
            return ["workspace/reviews/readiness.md", "workspace/artifacts/release_note.md"]
        raise AssertionError(f"Unsupported stage: {slug}")

    def _stage_markdown(self, stage, files: list[str]) -> str:
        key_results = "Validation passed."
        if stage.slug == "02_hypothesis_generation":
            key_results = "\n".join(
                [
                    "### Theoretical Propositions",
                    "- **T1**: Representation quality controls final accuracy.",
                    "  - Derived from: Stage 01 synthesis.",
                    "",
                    "### Empirical Hypotheses",
                    "- **H1**: Adding retrieval improves score by at least 2 points.",
                    "  - Depends on: retrieval pipeline.",
                    "  - Verification: compare against no-retrieval baseline.",
                    "",
                    "### Paper Claims (Provisional)",
                    "- **C1**: Retrieval makes the workflow more robust across tasks.",
                    "  - Status: provisional",
                ]
            )
        files_block = "\n".join(f"- `{path}` - generated in this stage" for path in files)
        return (
            f"# {stage.title}\n\n"
            "## Objective\n"
            f"{stage.objective}\n\n"
            "## Previously Approved Stage Summaries\n"
            "_None yet._\n\n"
            "## What I Did\n"
            "Executed the stage and wrote durable artifacts to the run workspace.\n\n"
            "## Key Results\n"
            f"{key_results}\n\n"
            "## Files Produced\n"
            f"{files_block}\n\n"
            "## Decision Ledger\n"
            "- **Open Questions**: How much headroom remains after this stage?\n"
            "- **Locked Decisions**: Keep the filesystem as the authority.\n"
            "- **Assumptions**: Current artifacts are sufficient for downstream stages.\n"
            "- **Rejected Alternatives**: Hidden transient state.\n\n"
            "## Suggestions for Refinement\n"
            "1. Tighten evaluation thresholds.\n"
            "2. Increase traceability.\n"
            "3. Expand ablations.\n\n"
            "## Your Options\n"
            "1. Use suggestion 1\n"
            "2. Use suggestion 2\n"
            "3. Use suggestion 3\n"
            "4. Refine with your own feedback\n"
            "5. Approve and continue\n"
            "6. Abort\n"
        )


class RepairingStageOperator(ScriptedStageOperator):
    def run_stage(self, request: StageRunRequest) -> StageRunResult:
        count = self.invocations.get(request.stage.slug, 0)
        if request.stage.slug == "01_literature_survey" and count == 0:
            self.invocations[request.stage.slug] = 1
            stage_file = request.workspace.stage_draft_path(request.stage.slug)
            write_text(stage_file, f"# {request.stage.title}\n\n## Objective\nbroken draft\n")
            return StageRunResult(success=True, stage_file_path=stage_file, session_ref="repair-needed")
        return super().run_stage(request)


class AutoResearchWorkflowTests(unittest.TestCase):
    def test_auto_research_workflow_runs_all_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progress_events: list[dict] = []
            workflow = AutoResearchWorkflow(operator=ScriptedStageOperator(), progress_sink=progress_events.append)
            result = workflow.run(goal="Study filesystem-native agent organizations.", runs_dir=Path(tmp))

            self.assertTrue(result.success)
            self.assertEqual(len(result.approved_stages), 8)
            self.assertTrue(result.workspace.stage_final_path("08_dissemination").exists())
            self.assertTrue(result.workspace.hypothesis_manifest.exists())
            self.assertTrue(result.workspace.experiment_manifest.exists())

            manifest = json.loads(result.workspace.run_manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["run_status"], "completed")
            self.assertEqual(len([entry for entry in manifest["stages"] if entry["approved"]]), 8)

            artifact_index = json.loads(result.workspace.artifact_index.read_text(encoding="utf-8"))
            self.assertGreaterEqual(artifact_index["artifact_count"], 12)
            self.assertIn("## Approved Stage Summaries", read_text(result.workspace.memory))
            progress_kinds = [event["kind"] for event in progress_events]
            self.assertIn("run_started", progress_kinds)
            self.assertIn("stage_started", progress_kinds)
            self.assertIn("stage_approved", progress_kinds)
            self.assertIn("run_completed", progress_kinds)

    def test_invalid_stage_can_be_repaired_inside_same_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow = AutoResearchWorkflow(operator=RepairingStageOperator())
            result = workflow.run(goal="Repair a bad stage summary.", runs_dir=Path(tmp))

            self.assertTrue(result.success)
            repair_state = result.workspace.operator_state_dir / "01_literature_survey.attempt_01.repair.json"
            self.assertTrue(repair_state.exists())
            final_text = read_text(result.workspace.stage_final_path("01_literature_survey"))
            self.assertIn("## Files Produced", final_text)


if __name__ == "__main__":
    unittest.main()
