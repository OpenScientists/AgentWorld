from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..controller.base import AgentController, ControllerResumeRequest, ControllerStartRequest
from ..workspace import append_jsonl, read_text, write_text
from .models import StageRepairRequest, StageRunRequest, StageRunResult


@dataclass(slots=True)
class ControllerStageOperator:
    """Stage operator backed by a real strong-agent controller."""

    controller: AgentController
    operator_id: str
    tool_policy: dict[str, Any] = field(default_factory=dict)
    timeout_s: int | None = None
    env: dict[str, str] = field(default_factory=dict)
    event_sink: Callable[[dict[str, Any]], None] | None = None

    def run_stage(self, request: StageRunRequest) -> StageRunResult:
        session_file = request.workspace.stage_session_file(request.stage.slug)
        session_id = read_text(session_file).strip() if request.continue_session else ""
        start_request = ControllerStartRequest(
            session_id=session_id or None,
            working_dir=request.workspace.run_root,
            instruction=request.prompt,
            tool_policy=dict(self.tool_policy),
            env=dict(self.env),
            timeout_s=self.timeout_s,
            metadata={
                "operator_id": self.operator_id,
                "workflow": "auto-research",
                "stage": request.stage.slug,
                "attempt": request.attempt,
                "run_root": str(request.workspace.run_root),
            },
        )
        if request.continue_session and session_id:
            handle = self.controller.resume(
                ControllerResumeRequest(
                    session_id=session_id,
                    working_dir=start_request.working_dir,
                    instruction=start_request.instruction,
                    attachments=list(start_request.attachments),
                    tool_policy=dict(start_request.tool_policy),
                    env=dict(start_request.env),
                    timeout_s=start_request.timeout_s,
                    metadata=dict(start_request.metadata),
                )
            )
        else:
            handle = self.controller.start(start_request)

        write_text(session_file, handle.session_id)
        events: list[dict[str, Any]] = []
        stdout_fragments: list[str] = []
        stderr_fragments: list[str] = []
        success = True

        for event in self.controller.stream(handle):
            event_payload = {
                "kind": event.kind,
                "payload": event.payload,
                "created_at": event.created_at,
            }
            events.append(event_payload)
            self._emit(
                {
                    "kind": "controller_event",
                    "stage": request.stage.slug,
                    "stage_title": request.stage.title,
                    "attempt": request.attempt,
                    "operator_id": self.operator_id,
                    "controller_event_kind": event.kind,
                    "payload": event.payload,
                    "created_at": event.created_at,
                }
            )
            append_jsonl(
                request.workspace.events,
                {
                    "kind": "controller_event",
                    "stage": request.stage.slug,
                    "attempt": request.attempt,
                    "operator_id": self.operator_id,
                    "event": event_payload,
                },
            )
            if event.kind in {"message_completed", "message_delta"}:
                text = event.payload.get("text")
                if isinstance(text, str):
                    stdout_fragments.append(text)
            elif event.kind == "completed":
                result_text = event.payload.get("result")
                if isinstance(result_text, str):
                    stdout_fragments.append(result_text)
            elif event.kind == "failed":
                success = False
                stderr_fragments.append(str(event.payload.get("message", "Controller execution failed.")))

        metadata = {
            "controller_handle": handle.metadata,
            "event_count": len(events),
            "session_ref": handle.session_id,
        }
        return StageRunResult(
            success=success,
            stage_file_path=request.workspace.stage_draft_path(request.stage.slug),
            stdout="\n".join(fragment for fragment in stdout_fragments if fragment),
            stderr="\n".join(fragment for fragment in stderr_fragments if fragment),
            session_ref=handle.session_id,
            metadata=metadata,
            events=tuple(events),
        )

    def _emit(self, event: dict[str, Any]) -> None:
        if self.event_sink is None:
            return
        self.event_sink(event)

    def repair_stage_summary(self, request: StageRepairRequest) -> StageRunResult:
        errors = "\n".join(f"- {error}" for error in request.validation_errors) or "- Stage draft was missing or invalid."
        prompt = "\n\n".join(
            [
                "# Repair Stage Summary",
                (
                    f"Repair {request.stage.title}. Continue the same provider session if possible. "
                    "Do not restart the whole research stage unless necessary."
                ),
                "# Required Action",
                (
                    f"Create or overwrite the complete stage summary at "
                    f"`{request.workspace.stage_draft_path(request.stage.slug).resolve()}`."
                ),
                "# Validation Errors To Fix",
                errors,
                "# Original Prompt",
                request.original_prompt[-12000:],
                "# Previous Result",
                (
                    f"success={request.original_result.success}\n"
                    f"stdout:\n{request.original_result.stdout[-4000:]}\n\n"
                    f"stderr:\n{request.original_result.stderr[-4000:]}"
                ),
            ]
        )
        return self.run_stage(
            StageRunRequest(
                stage=request.stage,
                prompt=prompt,
                workspace=request.workspace,
                attempt=request.attempt,
                continue_session=True,
            )
        )


def write_prompt_snapshot(path: Path, prompt: str) -> None:
    path.write_text(prompt.rstrip() + "\n", encoding="utf-8")


def event_payloads_to_json(events: tuple[dict[str, Any], ...]) -> str:
    return json.dumps(list(events), indent=2, ensure_ascii=True, default=str)
