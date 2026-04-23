from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..approval import ApprovalGate, AutoApproveGate
from ..artifacts import ArtifactRequirement, validate_artifact_requirements, write_artifact_index
from ..manifest import (
    RunManifest,
    ensure_run_manifest,
    initialize_run_manifest,
    load_run_manifest,
    mark_stage_approved_manifest,
    mark_stage_failed_manifest,
    mark_stage_review_manifest,
    mark_stage_running_manifest,
    rollback_to_stage,
    select_pending_stages,
    sync_stage_session_id,
    update_manifest_run_status,
)
from ..research import (
    validate_citation_verification,
    validate_experiment_manifest,
    validate_literature_evidence,
    write_experiment_manifest,
    write_hypothesis_manifest,
)
from ..stage import (
    StageOperator,
    StageRepairRequest,
    StageRunRequest,
    StageRunResult,
    StageSpec,
    append_approved_stage_summary,
    extract_path_references,
    extract_revision_delta,
    rebuild_memory_from_manifest,
    render_stage_prompt,
    strip_revision_delta,
    validate_stage_markdown,
    write_stage_handoff,
)
from ..utils import utc_now
from ..workspace import (
    RunWorkspace,
    append_jsonl,
    append_text,
    build_run_workspace,
    create_run_workspace,
    ensure_run_workspace,
    read_text,
    relative_to_run,
    write_json,
    write_text,
)


AutoResearchProgressSink = Callable[[dict[str, Any]], None]


AUTO_RESEARCH_STAGES: tuple[StageSpec, ...] = (
    StageSpec(
        number=1,
        slug="01_literature_survey",
        name="Literature Survey",
        objective="Build an auditable literature base and claim-to-source ledger.",
        artifact_requirements=(
            ArtifactRequirement("workspace/literature/survey.md", "Structured literature survey"),
            ArtifactRequirement("workspace/literature/sources.json", "Machine-readable source ledger"),
            ArtifactRequirement("workspace/literature/claims.json", "Claim-to-source evidence ledger"),
        ),
    ),
    StageSpec(
        number=2,
        slug="02_hypothesis_generation",
        name="Hypothesis Generation",
        objective="Turn the literature base into typed theoretical, empirical, and paper claims.",
        artifact_requirements=(
            ArtifactRequirement("workspace/notes/hypotheses.md", "Human-readable hypothesis notes"),
            ArtifactRequirement("workspace/notes/hypothesis_manifest.json", "Typed claim manifest"),
        ),
    ),
    StageSpec(
        number=3,
        slug="03_study_design",
        name="Study Design",
        objective="Design the study protocol, data interface, and evaluation plan.",
        artifact_requirements=(
            ArtifactRequirement("workspace/notes/study_design.md", "Study design"),
            ArtifactRequirement("workspace/data/study_design.json", "Machine-readable study design"),
        ),
    ),
    StageSpec(
        number=4,
        slug="04_implementation",
        name="Implementation",
        objective="Implement reusable code or analysis machinery required by the study.",
        artifact_requirements=(
            ArtifactRequirement("workspace/code/implementation.py", "Reference implementation"),
            ArtifactRequirement("workspace/data/config.json", "Runnable experiment configuration"),
        ),
    ),
    StageSpec(
        number=5,
        slug="05_experimentation",
        name="Experimentation",
        objective="Run experiments and preserve machine-readable outputs.",
        artifact_requirements=(
            ArtifactRequirement("workspace/results/results.json", "Machine-readable result summary"),
            ArtifactRequirement("workspace/results/experiment_manifest.json", "Experiment bundle manifest"),
        ),
    ),
    StageSpec(
        number=6,
        slug="06_analysis",
        name="Analysis",
        objective="Analyze results, failure modes, and evidence quality.",
        artifact_requirements=(
            ArtifactRequirement("workspace/results/analysis.md", "Result analysis"),
            ArtifactRequirement("workspace/figures/summary.svg", "Main analysis figure"),
        ),
    ),
    StageSpec(
        number=7,
        slug="07_writing",
        name="Writing",
        objective="Assemble a paper-style research report grounded in produced artifacts.",
        artifact_requirements=(
            ArtifactRequirement("workspace/writing/main.tex", "Manuscript entrypoint"),
            ArtifactRequirement("workspace/writing/references.bib", "Bibliography"),
            ArtifactRequirement("workspace/artifacts/build_log.txt", "Build log"),
            ArtifactRequirement("workspace/artifacts/citation_verification.json", "Citation verification ledger"),
            ArtifactRequirement("workspace/artifacts/self_review.json", "Self-review checklist"),
            ArtifactRequirement("workspace/artifacts/paper.pdf", "Compiled manuscript PDF"),
        ),
    ),
    StageSpec(
        number=8,
        slug="08_dissemination",
        name="Dissemination",
        objective="Prepare release notes, review artifacts, and downstream packaging guidance.",
        artifact_requirements=(
            ArtifactRequirement("workspace/reviews/readiness.md", "Release readiness review"),
            ArtifactRequirement("workspace/artifacts/release_note.md", "Release note"),
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class AutoResearchRunResult:
    success: bool
    workspace: RunWorkspace
    approved_stages: tuple[str, ...]
    failed_stage: str | None = None
    errors: tuple[str, ...] = ()


@dataclass(slots=True)
class AutoResearchWorkflow:
    operator: StageOperator
    approval_gate: ApprovalGate = field(default_factory=AutoApproveGate)
    stages: tuple[StageSpec, ...] = AUTO_RESEARCH_STAGES
    max_attempts: int = 3
    config: dict[str, Any] = field(default_factory=dict)
    progress_sink: AutoResearchProgressSink | None = None

    def run(
        self,
        *,
        goal: str,
        runs_dir: Path,
        run_id: str | None = None,
    ) -> AutoResearchRunResult:
        workspace = create_run_workspace(
            runs_dir=runs_dir,
            goal=goal,
            run_id=run_id,
            config={
                "workflow": "auto-research",
                "stage_count": len(self.stages),
                **dict(self.config),
            },
        )
        initialize_run_manifest(workspace, self.stages)
        write_artifact_index(workspace.artifact_index, workspace.workspace_root)
        write_experiment_manifest(workspace)
        append_text(workspace.logs, f"Run started at {utc_now()}\n")
        self._emit(
            "run_started",
            run_root=str(workspace.run_root),
            stage_count=len(self.stages),
            approval_mode=self.config.get("approval_mode"),
            backend=self.config.get("backend"),
        )
        return self._run_from_workspace(workspace)

    def resume(
        self,
        *,
        run_root: Path,
        start_stage: StageSpec | None = None,
        rollback_stage: StageSpec | None = None,
    ) -> AutoResearchRunResult:
        workspace = build_run_workspace(run_root)
        ensure_run_workspace(workspace)
        ensure_run_manifest(workspace, self.stages)
        if rollback_stage is not None:
            manifest = rollback_to_stage(workspace, self.stages, rollback_stage)
            approved = {entry.slug for entry in manifest.stages if entry.approved}
            rebuild_memory_from_manifest(workspace, self.stages, approved)
            start_stage = rollback_stage
        append_text(workspace.logs, f"Run resumed at {utc_now()}\n")
        self._emit(
            "run_resumed",
            run_root=str(workspace.run_root),
            start_stage=start_stage.slug if start_stage else None,
            rollback_stage=rollback_stage.slug if rollback_stage else None,
        )
        return self._run_from_workspace(workspace, start_stage=start_stage)

    def _run_from_workspace(
        self,
        workspace: RunWorkspace,
        start_stage: StageSpec | None = None,
    ) -> AutoResearchRunResult:
        approved = _approved_stage_slugs(load_run_manifest(workspace.run_manifest))
        stages_to_run = select_pending_stages(workspace, self.stages, start_stage=start_stage)
        self._emit(
            "stages_selected",
            run_root=str(workspace.run_root),
            stages=[stage.slug for stage in stages_to_run],
        )
        for stage in stages_to_run:
            ok, errors = self._run_stage(workspace, stage)
            if not ok:
                manifest = load_run_manifest(workspace.run_manifest)
                self._emit(
                    "run_failed",
                    run_root=str(workspace.run_root),
                    failed_stage=stage.slug,
                    errors=list(errors),
                )
                return AutoResearchRunResult(
                    success=False,
                    workspace=workspace,
                    approved_stages=_approved_stage_slugs(manifest),
                    failed_stage=stage.slug,
                    errors=tuple(errors),
                )
            approved = (*approved, stage.slug)

        update_manifest_run_status(
            workspace,
            self.stages,
            run_status="completed",
            last_event="run.completed",
            current_stage_slug=None,
            completed_at=utc_now(),
        )
        append_text(workspace.logs, f"Run completed at {utc_now()}\n")
        self._emit("run_completed", run_root=str(workspace.run_root), approved_stages=list(approved))
        return AutoResearchRunResult(success=True, workspace=workspace, approved_stages=tuple(approved))

    def _run_stage(self, workspace: RunWorkspace, stage: StageSpec) -> tuple[bool, list[str]]:
        manifest = ensure_run_manifest(workspace, self.stages)
        entry = next(item for item in manifest.stages if item.slug == stage.slug)
        attempt = entry.attempt_count + 1
        feedback: str | None = None
        continue_session = bool(entry.session_id)
        last_errors: tuple[str, ...] = ()

        for _ in range(self.max_attempts):
            write_text(workspace.stage_execution_marker_file(stage.slug), utc_now())
            mark_stage_running_manifest(workspace, self.stages, stage, attempt)
            self._emit(
                "stage_started",
                run_root=str(workspace.run_root),
                stage=stage.slug,
                stage_title=stage.title,
                attempt=attempt,
                continue_session=continue_session,
            )
            prompt = render_stage_prompt(
                stage=stage,
                workspace=workspace,
                feedback=feedback,
                continue_session=continue_session,
                attempt=attempt,
                previous_validation_errors=last_errors,
            )
            write_text(workspace.prompt_path(stage.slug, attempt), prompt)
            append_jsonl(
                workspace.events,
                {"kind": "stage_started", "stage": stage.slug, "attempt": attempt, "created_at": utc_now()},
            )

            self._emit(
                "operator_started",
                run_root=str(workspace.run_root),
                stage=stage.slug,
                stage_title=stage.title,
                attempt=attempt,
                prompt_path=str(workspace.prompt_path(stage.slug, attempt)),
            )
            result = self.operator.run_stage(
                StageRunRequest(
                    stage=stage,
                    prompt=prompt,
                    workspace=workspace,
                    attempt=attempt,
                    continue_session=continue_session,
                )
            )
            self._emit(
                "operator_finished",
                run_root=str(workspace.run_root),
                stage=stage.slug,
                stage_title=stage.title,
                attempt=attempt,
                success=result.success,
                session_ref=result.session_ref,
                event_count=len(result.events),
            )
            self._write_operator_state(workspace, stage, attempt, result)
            if result.session_ref:
                sync_stage_session_id(workspace, self.stages, stage, result.session_ref)

            result, errors = self._validate_or_repair_attempt(workspace, stage, attempt, prompt, result)
            if errors:
                mark_stage_failed_manifest(workspace, self.stages, stage, "; ".join(errors))
                self._emit(
                    "stage_validation_failed",
                    run_root=str(workspace.run_root),
                    stage=stage.slug,
                    stage_title=stage.title,
                    attempt=attempt,
                    errors=list(errors),
                )
                append_jsonl(
                    workspace.events,
                    {
                        "kind": "stage_validation_failed",
                        "stage": stage.slug,
                        "attempt": attempt,
                        "errors": errors,
                        "created_at": utc_now(),
                    },
                )
                feedback = (
                    "Continue the current stage conversation and fix the invalid stage output. "
                    "Preserve correct completed work. Validation errors:\n"
                    + "\n".join(f"- {error}" for error in errors)
                )
                last_errors = tuple(errors)
                continue_session = True
                attempt += 1
                continue

            markdown = read_text(result.stage_file_path)
            artifact_paths = tuple(extract_path_references(markdown))
            mark_stage_review_manifest(workspace, self.stages, stage, attempt, artifact_paths)
            self._emit(
                "stage_awaiting_review",
                run_root=str(workspace.run_root),
                stage=stage.slug,
                stage_title=stage.title,
                attempt=attempt,
                draft_path=str(result.stage_file_path),
                artifact_paths=list(artifact_paths),
            )
            decision = self.approval_gate.review(
                workspace=workspace,
                stage=stage,
                stage_markdown=markdown,
                attempt=attempt,
                validation_errors=[],
            )
            append_jsonl(
                workspace.events,
                {
                    "kind": "stage_reviewed",
                    "stage": stage.slug,
                    "attempt": attempt,
                    "decision": decision.action,
                    "reason": decision.reason,
                    "created_at": utc_now(),
                },
            )
            if decision.action == "approve":
                self._promote_stage(workspace, stage, result.stage_file_path, markdown, attempt, artifact_paths)
                self._emit(
                    "stage_approved",
                    run_root=str(workspace.run_root),
                    stage=stage.slug,
                    stage_title=stage.title,
                    attempt=attempt,
                    final_path=str(workspace.stage_final_path(stage.slug)),
                )
                return True, []
            if decision.action == "abort":
                update_manifest_run_status(
                    workspace,
                    self.stages,
                    run_status="cancelled",
                    last_event="run.cancelled",
                    current_stage_slug=stage.slug,
                    last_error=decision.reason or "Stage aborted by approval gate.",
                )
                self._emit(
                    "stage_aborted",
                    run_root=str(workspace.run_root),
                    stage=stage.slug,
                    stage_title=stage.title,
                    attempt=attempt,
                    reason=decision.reason,
                )
                return False, [decision.reason or "Stage aborted by approval gate."]
            self._emit(
                "stage_refine_requested",
                run_root=str(workspace.run_root),
                stage=stage.slug,
                stage_title=stage.title,
                attempt=attempt,
                feedback=decision.feedback,
            )
            feedback = decision.feedback or "Human or automated reviewer requested refinement."
            continue_session = True
            attempt += 1

        error = f"Stage exceeded max_attempts={self.max_attempts}."
        mark_stage_failed_manifest(workspace, self.stages, stage, error)
        self._emit(
            "stage_failed",
            run_root=str(workspace.run_root),
            stage=stage.slug,
            stage_title=stage.title,
            attempt=attempt,
            error=error,
        )
        return False, list(last_errors or (error,))

    def _validate_or_repair_attempt(
        self,
        workspace: RunWorkspace,
        stage: StageSpec,
        attempt: int,
        prompt: str,
        result: StageRunResult,
    ) -> tuple[StageRunResult, list[str]]:
        errors = self._validate_stage_result(workspace, stage, result)
        if not errors:
            self._emit(
                "stage_validated",
                run_root=str(workspace.run_root),
                stage=stage.slug,
                stage_title=stage.title,
                attempt=attempt,
            )
            return result, []
        self._emit(
            "stage_repair_started",
            run_root=str(workspace.run_root),
            stage=stage.slug,
            stage_title=stage.title,
            attempt=attempt,
            errors=list(errors),
        )
        repair_result = self._repair_stage(workspace, stage, attempt, prompt, result, tuple(errors))
        if repair_result is result:
            return result, errors
        self._write_operator_state(workspace, stage, attempt, repair_result, suffix="repair")
        if repair_result.session_ref:
            sync_stage_session_id(workspace, self.stages, stage, repair_result.session_ref)
        return repair_result, self._validate_stage_result(workspace, stage, repair_result)

    def _validate_stage_result(
        self,
        workspace: RunWorkspace,
        stage: StageSpec,
        result: StageRunResult,
    ) -> list[str]:
        errors: list[str] = []
        if not result.success:
            errors.append(result.stderr or "Stage operator returned failure.")
        if not result.stage_file_path.exists():
            errors.append(f"Missing stage draft: {relative_to_run(workspace, result.stage_file_path)}")
            return errors

        markdown = read_text(result.stage_file_path)
        revision_delta = extract_revision_delta(markdown)
        if revision_delta:
            markdown = strip_revision_delta(markdown)
            write_text(result.stage_file_path, markdown)
        self._post_draft_structured_artifacts(workspace, stage, markdown)
        errors.extend(validate_stage_markdown(markdown, stage, workspace=workspace).errors)
        errors.extend(
            validate_artifact_requirements(run_root=workspace.run_root, requirements=stage.artifact_requirements).errors
        )
        errors.extend(self._validate_auto_research_artifacts(workspace, stage))
        return errors

    def _repair_stage(
        self,
        workspace: RunWorkspace,
        stage: StageSpec,
        attempt: int,
        prompt: str,
        result: StageRunResult,
        errors: tuple[str, ...],
    ) -> StageRunResult:
        repair = getattr(self.operator, "repair_stage_summary", None)
        if not callable(repair):
            return result
        append_jsonl(
            workspace.events,
            {
                "kind": "stage_repair_started",
                "stage": stage.slug,
                "attempt": attempt,
                "errors": list(errors),
                "created_at": utc_now(),
            },
        )
        return repair(
            StageRepairRequest(
                stage=stage,
                original_prompt=prompt,
                original_result=result,
                workspace=workspace,
                attempt=attempt,
                validation_errors=errors,
            )
        )

    def _post_draft_structured_artifacts(self, workspace: RunWorkspace, stage: StageSpec, markdown: str) -> None:
        if stage.slug == "02_hypothesis_generation":
            write_hypothesis_manifest(workspace, markdown)
        if stage.number >= 5:
            write_experiment_manifest(workspace)

    def _validate_auto_research_artifacts(self, workspace: RunWorkspace, stage: StageSpec) -> list[str]:
        problems: list[str] = []
        if stage.number == 1:
            problems.extend(f"{stage.title}: {problem}" for problem in validate_literature_evidence(workspace))
        if stage.number >= 5:
            problems.extend(f"{stage.title}: {problem}" for problem in validate_experiment_manifest(workspace.experiment_manifest))
        if stage.number >= 7:
            citation_path = workspace.artifacts_dir / "citation_verification.json"
            problems.extend(f"{stage.title}: {problem}" for problem in validate_citation_verification(citation_path))
        return problems

    def _promote_stage(
        self,
        workspace: RunWorkspace,
        stage: StageSpec,
        draft_path: Path,
        markdown: str,
        attempt: int,
        artifact_paths: tuple[str, ...],
    ) -> None:
        final_path = workspace.stage_final_path(stage.slug)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if draft_path.resolve() != final_path.resolve():
            shutil.copyfile(draft_path, final_path)
        append_approved_stage_summary(workspace, stage, markdown)
        write_stage_handoff(workspace, stage, markdown)
        write_artifact_index(workspace.artifact_index, workspace.workspace_root)
        write_experiment_manifest(workspace)
        mark_stage_approved_manifest(workspace, self.stages, stage, attempt, artifact_paths)
        append_text(workspace.logs, f"Approved {stage.title} at {utc_now()}\n")

    def _write_operator_state(
        self,
        workspace: RunWorkspace,
        stage: StageSpec,
        attempt: int,
        result: StageRunResult,
        *,
        suffix: str = "",
    ) -> None:
        path = workspace.operator_state_path(stage.slug, attempt)
        if suffix:
            path = path.with_name(f"{path.stem}.{suffix}{path.suffix}")
        write_json(
            path,
            {
                "stage": stage.slug,
                "attempt": attempt,
                "success": result.success,
                "stage_file_path": str(result.stage_file_path),
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
                "session_ref": result.session_ref,
                "metadata": result.metadata,
                "event_count": len(result.events),
                "updated_at": utc_now(),
            },
        )

    def _emit(self, kind: str, **payload: Any) -> None:
        if self.progress_sink is None:
            return
        event = {"kind": kind, "created_at": utc_now(), **payload}
        self.progress_sink(event)


def _approved_stage_slugs(manifest: RunManifest | None) -> tuple[str, ...]:
    if manifest is None:
        return ()
    return tuple(entry.slug for entry in manifest.stages if entry.approved)
