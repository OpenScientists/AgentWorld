from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from ..stage import StageSpec
from ..workspace import RunWorkspace

ApprovalAction = Literal["approve", "refine", "abort"]


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    action: ApprovalAction
    reason: str = ""
    feedback: str = ""

    @property
    def approved(self) -> bool:
        return self.action == "approve"


class ApprovalGate(Protocol):
    def review(
        self,
        *,
        workspace: RunWorkspace,
        stage: StageSpec,
        stage_markdown: str,
        attempt: int,
        validation_errors: list[str],
    ) -> ApprovalDecision:
        ...


class AutoApproveGate:
    def review(
        self,
        *,
        workspace: RunWorkspace,
        stage: StageSpec,
        stage_markdown: str,
        attempt: int,
        validation_errors: list[str],
    ) -> ApprovalDecision:
        if validation_errors:
            return ApprovalDecision(
                action="refine",
                reason="Validation failed.",
                feedback="\n".join(validation_errors),
            )
        return ApprovalDecision(action="approve", reason="Auto-approved after validation.")


class AbortOnValidationFailureGate:
    def review(
        self,
        *,
        workspace: RunWorkspace,
        stage: StageSpec,
        stage_markdown: str,
        attempt: int,
        validation_errors: list[str],
    ) -> ApprovalDecision:
        if validation_errors:
            return ApprovalDecision(
                action="abort",
                reason="Validation failed.",
                feedback="\n".join(validation_errors),
            )
        return ApprovalDecision(action="approve", reason="Approved after validation.")


class TerminalApprovalGate:
    def review(
        self,
        *,
        workspace: RunWorkspace,
        stage: StageSpec,
        stage_markdown: str,
        attempt: int,
        validation_errors: list[str],
    ) -> ApprovalDecision:
        print()
        print(f"Review required for {stage.title} attempt {attempt}")
        print(f"Draft: {workspace.stage_draft_path(stage.slug)}")
        if validation_errors:
            print("Validation errors:")
            for error in validation_errors:
                print(f"- {error}")
            print("The stage cannot be approved until these errors are fixed.")
        else:
            print("Validation passed.")
        print()
        print("Options:")
        print("1. Approve and continue")
        print("2. Refine with feedback")
        print("3. Abort")
        while True:
            choice = input("Select [1/2/3]: ").strip()
            if choice == "1":
                if validation_errors:
                    return ApprovalDecision(
                        action="refine",
                        reason="Validation failed; approval was blocked.",
                        feedback="\n".join(validation_errors),
                    )
                return ApprovalDecision(action="approve", reason="Human approved in terminal.")
            if choice == "2":
                print("Enter feedback. Finish with an empty line.")
                lines: list[str] = []
                while True:
                    line = input()
                    if not line:
                        break
                    lines.append(line)
                feedback = "\n".join(lines).strip() or "\n".join(validation_errors)
                return ApprovalDecision(action="refine", reason="Human requested refinement.", feedback=feedback)
            if choice == "3":
                return ApprovalDecision(action="abort", reason="Human aborted in terminal.")
            print("Invalid choice.")
