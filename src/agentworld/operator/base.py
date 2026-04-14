from __future__ import annotations

import json
from typing import Any, Protocol

from ..controller.base import (
    AgentController,
    ControllerEvent,
    ControllerResumeRequest,
    ControllerRunHandle,
    ControllerStartRequest,
)
from ..protocol.a2a import A2AEnvelope, Handoff
from ..protocol.artifacts import Artifact
from ..skill_loader import LoadedSkill, load_skills
from ..utils import utc_now
from .models import (
    OperatorError,
    OperatorRequest,
    OperatorResult,
    OperatorResumeRequest,
    RuntimeContext,
)


class Operator(Protocol):
    def invoke(self, request: OperatorRequest, runtime: RuntimeContext) -> OperatorResult:
        ...

    def resume(self, request: OperatorResumeRequest, runtime: RuntimeContext) -> OperatorResult:
        ...


class DefaultOperator:
    def __init__(
        self,
        operator_id: str,
        controller: AgentController,
        *,
        role: str | None = None,
        instruction_prefix: str | None = None,
    ) -> None:
        self.operator_id = operator_id
        self.controller = controller
        self.role = role or operator_id
        self.instruction_prefix = instruction_prefix or ""

    def invoke(self, request: OperatorRequest, runtime: RuntimeContext) -> OperatorResult:
        loaded_skills = self._load_skills(request)
        start_request = ControllerStartRequest(
            session_id=request.metadata.get("session_id"),
            working_dir=request.working_dir,
            instruction=self._build_instruction(request, loaded_skills),
            tool_policy=request.tool_policy.to_dict(),
            timeout_s=request.timeout_s,
            metadata={
                "graph_id": runtime.graph_id,
                "node_name": runtime.node_name,
                "skills": list(request.skills),
                "skill_paths": [str(skill.skill_file) for skill in loaded_skills],
            },
        )
        handle = self.controller.start(start_request)
        return self._collect_result(request, runtime, handle)

    def resume(self, request: OperatorResumeRequest, runtime: RuntimeContext) -> OperatorResult:
        loaded_skills = self._load_skills(request)
        resume_request = ControllerResumeRequest(
            session_id=request.session_ref,
            working_dir=request.working_dir,
            instruction=self._build_instruction(request, loaded_skills),
            tool_policy=request.tool_policy.to_dict(),
            timeout_s=request.timeout_s,
            metadata={
                "graph_id": runtime.graph_id,
                "node_name": runtime.node_name,
                "skills": list(request.skills),
                "skill_paths": [str(skill.skill_file) for skill in loaded_skills],
            },
        )
        handle = self.controller.resume(resume_request)
        return self._collect_result(request, runtime, handle)

    def _build_instruction(self, request: OperatorRequest, loaded_skills: list[LoadedSkill]) -> str:
        payload = {
            "role": request.role,
            "objective": request.objective,
            "state_view": request.state_view,
            "inbox": [message.to_dict() for message in request.inbox],
            "artifacts": [artifact.to_dict() for artifact in request.artifacts],
            "skills": list(request.skills),
            "loaded_skills": [skill.to_dict() for skill in loaded_skills],
            "metadata": request.metadata,
        }
        rendered = json.dumps(payload, indent=2, ensure_ascii=True, default=str)
        if self.instruction_prefix:
            return f"{self.instruction_prefix}\n\n{rendered}"
        return rendered

    def _load_skills(self, request: OperatorRequest) -> list[LoadedSkill]:
        if not request.skills:
            return []
        return load_skills(request.skills, working_dir=request.working_dir)

    def _collect_result(
        self,
        request: OperatorRequest,
        runtime: RuntimeContext,
        handle: ControllerRunHandle,
    ) -> OperatorResult:
        messages: list[A2AEnvelope] = []
        artifacts: list[Artifact] = []
        handoffs: list[Handoff] = []
        state_patch: dict[str, Any] = {}
        status = "success"
        error: OperatorError | None = None
        trace_ref: str | None = None
        text_fragments: list[str] = []

        for event in self.controller.stream(handle):
            self._consume_event(
                event=event,
                request=request,
                runtime=runtime,
                messages=messages,
                artifacts=artifacts,
                handoffs=handoffs,
                state_patch=state_patch,
                text_fragments=text_fragments,
            )
            if event.kind == "failed":
                status = "failed"
                error = OperatorError(
                    code=str(event.payload.get("code", "controller_failed")),
                    message=str(event.payload.get("message", "Controller execution failed.")),
                    details=dict(event.payload.get("details", {})),
                )
                trace_ref = event.payload.get("trace_ref")
            elif event.kind == "completed":
                trace_ref = event.payload.get("trace_ref", trace_ref)
                status = str(event.payload.get("status", status))

        if text_fragments:
            messages.append(
                A2AEnvelope(
                    thread_id=runtime.thread_id,
                    sender=runtime.node_name,
                    receiver=None,
                    kind="observation",
                    payload={"text": "".join(text_fragments)},
                    created_at=utc_now(),
                )
            )

        return OperatorResult(
            status=status,  # type: ignore[arg-type]
            session_ref=handle.session_id,
            messages=messages,
            state_patch=state_patch,
            artifacts=artifacts,
            handoffs=handoffs,
            trace_ref=trace_ref,
            error=error,
        )

    def _consume_event(
        self,
        *,
        event: ControllerEvent,
        request: OperatorRequest,
        runtime: RuntimeContext,
        messages: list[A2AEnvelope],
        artifacts: list[Artifact],
        handoffs: list[Handoff],
        state_patch: dict[str, Any],
        text_fragments: list[str],
    ) -> None:
        payload = event.payload
        if event.kind == "message_delta":
            text = payload.get("text")
            if isinstance(text, str):
                text_fragments.append(text)
            return

        if event.kind == "message_completed":
            messages.append(
                A2AEnvelope(
                    thread_id=runtime.thread_id,
                    sender=runtime.node_name,
                    receiver=payload.get("receiver"),
                    kind=str(payload.get("kind", "observation")),
                    payload={"text": str(payload.get("text", ""))},
                    created_at=event.created_at,
                )
            )
            return

        if event.kind == "artifact_created":
            artifacts.append(
                Artifact(
                    kind=str(payload.get("kind", "file")),
                    path=payload.get("path"),
                    uri=payload.get("uri"),
                    description=payload.get("description"),
                    metadata=dict(payload.get("metadata", {})),
                )
            )
            return

        if event.kind == "tool_call":
            messages.append(
                A2AEnvelope(
                    thread_id=runtime.thread_id,
                    sender=runtime.node_name,
                    receiver=None,
                    kind="tool_call",
                    payload={
                        "id": payload.get("id"),
                        "name": payload.get("name"),
                        "input": payload.get("input", {}),
                    },
                    created_at=event.created_at,
                )
            )
            return

        if event.kind == "tool_result":
            messages.append(
                A2AEnvelope(
                    thread_id=runtime.thread_id,
                    sender=runtime.node_name,
                    receiver=None,
                    kind="tool_result",
                    payload={
                        "tool_use_id": payload.get("tool_use_id"),
                        "content": payload.get("content"),
                    },
                    created_at=event.created_at,
                )
            )
            return

        if event.kind == "state_hint":
            state_patch.update(dict(payload.get("state_patch", {})))
            return

        if event.kind == "completed":
            state_patch.update(dict(payload.get("state_patch", {})))
            for raw_handoff in payload.get("handoffs", []):
                handoffs.append(
                    Handoff(
                        target_node=str(raw_handoff["target_node"]),
                        task=str(raw_handoff["task"]),
                        payload=dict(raw_handoff.get("payload", {})),
                    )
                )
            return

        if event.kind == "handoff":
            handoffs.append(
                Handoff(
                    target_node=str(payload["target_node"]),
                    task=str(payload["task"]),
                    payload=dict(payload.get("payload", {})),
                )
            )

    def __repr__(self) -> str:
        return f"DefaultOperator(operator_id={self.operator_id!r}, role={self.role!r})"
