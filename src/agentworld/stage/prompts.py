from __future__ import annotations

from ..artifacts import format_artifact_index_for_prompt, write_artifact_index
from ..research import (
    build_writing_manifest,
    format_experiment_manifest_for_prompt,
    format_hypothesis_manifest_for_prompt,
    format_writing_manifest_for_prompt,
    load_hypothesis_manifest,
    write_experiment_manifest,
)
from ..workspace import RunWorkspace, read_text
from .handoff import build_decision_ledger_context, build_handoff_context
from .models import StageSpec, required_stage_template


def render_stage_prompt(
    *,
    stage: StageSpec,
    workspace: RunWorkspace,
    feedback: str | None = None,
    continue_session: bool = False,
    attempt: int = 1,
    previous_validation_errors: tuple[str, ...] | list[str] | None = None,
) -> str:
    template = stage.prompt_template.strip() or default_stage_prompt(stage)
    artifact_requirements = "\n".join(
        f"- `{requirement.relative_path}`: {requirement.description or 'required artifact'}"
        for requirement in stage.artifact_requirements
    ) or "- No explicit artifact requirements for this stage."
    artifact_index = write_artifact_index(workspace.artifact_index, workspace.workspace_root)
    structured_context = _build_structured_context(stage, workspace, artifact_index)
    continuation_context = _build_continuation_context(stage, workspace, attempt, previous_validation_errors)
    replacements = {
        "{{STAGE_TITLE}}": stage.title,
        "{{STAGE_SLUG}}": stage.slug,
        "{{STAGE_OUTPUT_PATH}}": str(workspace.stage_draft_path(stage.slug).resolve()),
        "{{STAGE_FINAL_OUTPUT_PATH}}": str(workspace.stage_final_path(stage.slug).resolve()),
        "{{RUN_ROOT}}": str(workspace.run_root.resolve()),
        "{{WORKSPACE_ROOT}}": str(workspace.workspace_root.resolve()),
        "{{GOAL}}": read_text(workspace.goal).strip(),
        "{{MEMORY}}": read_text(workspace.memory).strip(),
        "{{FEEDBACK}}": feedback.strip() if feedback else "None.",
        "{{ARTIFACT_REQUIREMENTS}}": artifact_requirements,
        "{{HANDOFF_CONTEXT}}": build_handoff_context(workspace, upto_stage=stage),
        "{{STRUCTURED_CONTEXT}}": structured_context,
        "{{CONTINUATION_CONTEXT}}": continuation_context if continue_session else "This is a fresh stage attempt.",
        "{{REQUIRED_STAGE_TEMPLATE}}": required_stage_template(stage),
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered.rstrip() + "\n"


def default_stage_prompt(stage: StageSpec) -> str:
    return "\n\n".join(
        [
            "# Stage Instructions",
            f"You are running {{STAGE_TITLE}}.",
            stage.objective or "Complete this stage using the run workspace.",
            "# Run Workspace",
            "- Run root: `{{RUN_ROOT}}`",
            "- Workspace root: `{{WORKSPACE_ROOT}}`",
            "- Stage draft output path: `{{STAGE_OUTPUT_PATH}}`",
            "- Stage final output path: `{{STAGE_FINAL_OUTPUT_PATH}}`",
            "# User Goal",
            "{{GOAL}}",
            "# Approved Memory",
            "{{MEMORY}}",
            "# Stage Handoff Context",
            "{{HANDOFF_CONTEXT}}",
            "# Structured Run Context",
            "{{STRUCTURED_CONTEXT}}",
            "# Required Artifacts",
            (
                "You must create every required artifact below before writing the stage summary. "
                "Use the paths exactly as written, relative to the run root."
            ),
            "{{ARTIFACT_REQUIREMENTS}}",
            "# Stage-Specific Contract",
            stage_specific_contract(stage),
            "# Feedback",
            "{{FEEDBACK}}",
            "# Continuation Context",
            "{{CONTINUATION_CONTEXT}}",
            "# Execution Rules",
            (
                "1. This is a real workflow run, not a toy demonstration.\n"
                "2. Use the filesystem as the source of truth.\n"
                "3. Do not invent artifact paths in the summary unless the files actually exist.\n"
                "4. Do not leave placeholders, TODOs, or unfinished sections.\n"
                "5. If a required artifact cannot be produced, explain the blocker in the stage summary and stop."
            ),
            "# Required Stage Summary",
            "Write the stage summary to `{{STAGE_OUTPUT_PATH}}` using this exact structure:",
            "```md\n{{REQUIRED_STAGE_TEMPLATE}}\n```",
        ]
    )


def stage_specific_contract(stage: StageSpec) -> str:
    if stage.slug == "02_hypothesis_generation":
        return (
            "For Stage 02, the `## Key Results` section must contain exactly these typed subsections: "
            "`### Theoretical Propositions`, `### Empirical Hypotheses`, and "
            "`### Paper Claims (Provisional)`. Each subsection must include at least one explicit ID. "
            "Use `TH-01`, `TH-02`, ... for theoretical propositions, `EH-01`, `EH-02`, ... for empirical "
            "hypotheses, and `PC-01`, `PC-02`, ... for paper claims. Markdown tables are acceptable, "
            "but the first column must be `ID`. Also write `workspace/notes/hypothesis_manifest.json` "
            "with non-empty theoretical, empirical, and paper-claim entries."
        )
    return "No additional stage-specific contract."


def _build_structured_context(stage: StageSpec, workspace: RunWorkspace, artifact_index) -> str:
    sections = [
        "## Artifact Index",
        f"Run-wide artifact index: `{workspace.artifact_index.resolve()}`",
        format_artifact_index_for_prompt(artifact_index),
    ]
    ledger_context = build_decision_ledger_context(workspace, upto_stage=stage)
    if ledger_context and stage.number >= 2:
        sections.extend(
            [
                "## Decision Ledger From Prior Stages",
                (
                    "Respect locked decisions and accepted assumptions. "
                    "Address open questions when relevant."
                ),
                ledger_context,
            ]
        )
    hypothesis_manifest = load_hypothesis_manifest(workspace.hypothesis_manifest)
    if hypothesis_manifest is not None and stage.number >= 3:
        sections.extend(
            [
                "## Hypothesis Context From Stage 02",
                "Typed claims approved in Stage 02:",
                format_hypothesis_manifest_for_prompt(hypothesis_manifest),
            ]
        )
    if stage.number >= 5:
        experiment_manifest = write_experiment_manifest(workspace)
        sections.extend(
            [
                "## Experiment Bundle Manifest",
                f"Standard experiment manifest: `{workspace.experiment_manifest.resolve()}`",
                format_experiment_manifest_for_prompt(experiment_manifest),
            ]
        )
    if stage.slug == "07_writing":
        writing_manifest = build_writing_manifest(workspace)
        sections.extend(
            [
                "## Writing Manifest",
                format_writing_manifest_for_prompt(writing_manifest),
            ]
        )
    return "\n\n".join(section.strip() for section in sections if section.strip())


def _build_continuation_context(
    stage: StageSpec,
    workspace: RunWorkspace,
    attempt: int,
    previous_validation_errors: tuple[str, ...] | list[str] | None,
) -> str:
    lines = [
        f"You are continuing {stage.title} in the same provider session.",
        f"Attempt: {attempt}",
        f"Current draft path: `{workspace.stage_draft_path(stage.slug).resolve()}`",
        f"Last promoted stage path: `{workspace.stage_final_path(stage.slug).resolve()}`",
        "Preserve valid completed work unless the feedback requires changing it.",
        "Insert `## Revision Delta` immediately after the top-level stage heading for refinement attempts.",
    ]
    if previous_validation_errors:
        lines.append("Previous validation errors:")
        lines.extend(f"- {error}" for error in previous_validation_errors)
    return "\n".join(lines)
