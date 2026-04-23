from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..artifacts import ArtifactRequirement
from ..workspace import RunWorkspace
from .markdown import FIXED_STAGE_OPTIONS, REQUIRED_STAGE_HEADINGS, StageValidationResult, validate_stage_markdown


@dataclass(frozen=True, slots=True)
class StageSpec:
    number: int
    slug: str
    name: str
    objective: str = ""
    prompt_template: str = ""
    artifact_requirements: tuple[ArtifactRequirement, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return f"Stage {self.number:02d}: {self.name}"


@dataclass(frozen=True, slots=True)
class StageRunRequest:
    stage: StageSpec
    prompt: str
    workspace: RunWorkspace
    attempt: int = 1
    continue_session: bool = False


@dataclass(frozen=True, slots=True)
class StageRepairRequest:
    stage: StageSpec
    original_prompt: str
    original_result: "StageRunResult"
    workspace: RunWorkspace
    attempt: int
    validation_errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StageRunResult:
    success: bool
    stage_file_path: Path
    stdout: str = ""
    stderr: str = ""
    session_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    events: tuple[dict[str, Any], ...] = ()


class StageOperator(Protocol):
    def run_stage(self, request: StageRunRequest) -> StageRunResult:
        ...


def required_stage_template(stage: StageSpec) -> str:
    key_results_template = "[Present the main results, findings, conclusions, or concrete outputs for this stage.]"
    if stage.slug == "02_hypothesis_generation":
        key_results_template = (
            "### Theoretical Propositions\n"
            "| ID | Statement | Derived From | Verification |\n"
            "| --- | --- | --- | --- |\n"
            "| TH-01 | [theoretical proposition] | [source claim ids] | [how it will be checked] |\n\n"
            "### Empirical Hypotheses\n"
            "| ID | Statement | Derived From | Verification |\n"
            "| --- | --- | --- | --- |\n"
            "| EH-01 | [empirical hypothesis] | [source claim ids] | [experiment or metric] |\n\n"
            "### Paper Claims (Provisional)\n"
            "| ID | Statement | Derived From | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| PC-01 | [paper-level claim] | [source claim ids] | provisional |"
        )
    return (
        f"# {stage.title}\n\n"
        "## Objective\n"
        "[State the exact objective of this stage.]\n\n"
        "## Previously Approved Stage Summaries\n"
        "[Summarize approved earlier stages from memory, or write _None yet._]\n\n"
        "## What I Did\n"
        "[Describe what you actually did in this stage.]\n\n"
        "## Key Results\n"
        f"{key_results_template}\n\n"
        "## Files Produced\n"
        "- `[relative/path]` - [what it contains]\n\n"
        "## Decision Ledger\n"
        "- **Open Questions**: [unresolved questions to carry forward to later stages]\n"
        "- **Locked Decisions**: [design or method decisions made in this stage, with rationale]\n"
        "- **Assumptions**: [accepted assumptions that downstream stages must respect]\n"
        "- **Rejected Alternatives**: [what was considered and why it was dropped]\n\n"
        "## Suggestions for Refinement\n"
        "1. [Suggestion 1]\n"
        "2. [Suggestion 2]\n"
        "3. [Suggestion 3]\n\n"
        "## Your Options\n"
        + "\n".join(FIXED_STAGE_OPTIONS)
        + "\n"
    )
