from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

from ..protocol.a2a import A2AEnvelope, Handoff
from ..protocol.artifacts import Artifact

OperatorStatus = Literal["success", "failed", "interrupted", "timeout"]
SessionPolicy = Literal["new", "reuse", "resume"]


@dataclass(slots=True)
class ToolPolicy:
    mode: str = "inherit"
    allowed_tools: list[str] = field(default_factory=list)
    permissions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "allowed_tools": list(self.allowed_tools),
            "permissions": dict(self.permissions),
        }


@dataclass(slots=True)
class OperatorMetrics:
    duration_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0


@dataclass(slots=True)
class OperatorError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuntimeContext:
    graph_id: str
    run_id: str
    thread_id: str
    node_name: str
    context: Mapping[str, Any] = field(default_factory=dict)
    working_dir: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OperatorRequest:
    operator_id: str
    role: str
    objective: str
    state_view: Mapping[str, Any] = field(default_factory=dict)
    inbox: list[A2AEnvelope] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    working_dir: Path | None = None
    session_policy: SessionPolicy = "new"
    tool_policy: ToolPolicy = field(default_factory=ToolPolicy)
    timeout_s: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OperatorResumeRequest(OperatorRequest):
    session_ref: str | None = None
    session_policy: SessionPolicy = "resume"


@dataclass(slots=True)
class OperatorResult:
    status: OperatorStatus = "success"
    session_ref: str | None = None
    messages: list[A2AEnvelope] = field(default_factory=list)
    state_patch: dict[str, Any] = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)
    handoffs: list[Handoff] = field(default_factory=list)
    metrics: OperatorMetrics = field(default_factory=OperatorMetrics)
    trace_ref: str | None = None
    error: OperatorError | None = None

    @property
    def is_success(self) -> bool:
        return self.status == "success"
