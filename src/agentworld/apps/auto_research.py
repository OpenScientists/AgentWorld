from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..approval import AutoApproveGate, TerminalApprovalGate
from ..controller.claude_code import ClaudeCodeController
from ..stage import ControllerStageOperator
from ..workflows import AutoResearchRunResult, AutoResearchWorkflow

BackendName = Literal["claude-code"]
ApprovalMode = Literal["manual", "validation-only"]
DEFAULT_AUTO_RESEARCH_TOOLS = ("Read", "Write", "Edit", "Bash", "Grep", "Glob")


@dataclass(frozen=True, slots=True)
class AutoResearchAppConfig:
    backend: BackendName = "claude-code"
    approval_mode: ApprovalMode = "manual"
    model: str | None = None
    claude_command: str = "claude"
    permission_mode: str = "default"
    tools: tuple[str, ...] = DEFAULT_AUTO_RESEARCH_TOOLS
    timeout_s: int = 14400
    max_attempts: int = 3


@dataclass(slots=True)
class AutoResearchApp:
    config: AutoResearchAppConfig
    workflow: AutoResearchWorkflow

    def run(
        self,
        *,
        goal: str,
        runs_dir: Path,
        run_id: str | None = None,
    ) -> AutoResearchRunResult:
        return self.workflow.run(goal=goal, runs_dir=runs_dir, run_id=run_id)


def create_auto_research_app(
    *,
    backend: BackendName = "claude-code",
    approval_mode: ApprovalMode = "manual",
    model: str | None = None,
    claude_command: str = "claude",
    permission_mode: str = "default",
    tools: tuple[str, ...] | list[str] | None = None,
    timeout_s: int = 14400,
    max_attempts: int = 3,
) -> AutoResearchApp:
    config = AutoResearchAppConfig(
        backend=backend,
        approval_mode=approval_mode,
        model=model,
        claude_command=claude_command,
        permission_mode=permission_mode,
        tools=tuple(tools or DEFAULT_AUTO_RESEARCH_TOOLS),
        timeout_s=timeout_s,
        max_attempts=max_attempts,
    )
    if backend != "claude-code":
        raise ValueError(f"Unsupported auto-research backend: {backend}")

    controller = ClaudeCodeController(
        command=config.claude_command,
        model=config.model,
        permission_mode=config.permission_mode,
    )
    operator = ControllerStageOperator(
        controller=controller,
        operator_id="claude-code-auto-research",
        tool_policy={
            "mode": config.permission_mode,
            "allowed_tools": list(config.tools),
            "permissions": {"permission_mode": config.permission_mode},
        },
        timeout_s=config.timeout_s,
    )
    approval_gate = AutoApproveGate() if config.approval_mode == "validation-only" else TerminalApprovalGate()
    workflow = AutoResearchWorkflow(
        operator=operator,
        approval_gate=approval_gate,
        max_attempts=config.max_attempts,
        config={
            "backend": config.backend,
            "model": config.model or "default",
            "approval_mode": config.approval_mode,
        },
    )
    return AutoResearchApp(config=config, workflow=workflow)


def run_auto_research(
    *,
    goal: str,
    runs_dir: Path,
    run_id: str | None = None,
    backend: BackendName = "claude-code",
    approval_mode: ApprovalMode = "manual",
    model: str | None = None,
    claude_command: str = "claude",
    permission_mode: str = "default",
    tools: tuple[str, ...] | list[str] | None = None,
    timeout_s: int = 14400,
    max_attempts: int = 3,
) -> AutoResearchRunResult:
    app = create_auto_research_app(
        backend=backend,
        approval_mode=approval_mode,
        model=model,
        claude_command=claude_command,
        permission_mode=permission_mode,
        tools=tools,
        timeout_s=timeout_s,
        max_attempts=max_attempts,
    )
    return app.run(goal=goal, runs_dir=runs_dir, run_id=run_id)
