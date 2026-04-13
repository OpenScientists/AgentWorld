from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol
from uuid import uuid4

from ..utils import utc_now


@dataclass(slots=True)
class ControllerEvent:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ControllerRunHandle:
    session_id: str
    events: list[ControllerEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ControllerStartRequest:
    session_id: str | None = None
    working_dir: Path | None = None
    instruction: str = ""
    attachments: list[str] = field(default_factory=list)
    tool_policy: dict[str, Any] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    timeout_s: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ControllerResumeRequest(ControllerStartRequest):
    session_id: str | None = None


class AgentController(Protocol):
    def start(self, request: ControllerStartRequest) -> ControllerRunHandle:
        ...

    def resume(self, request: ControllerResumeRequest) -> ControllerRunHandle:
        ...

    def stream(self, handle: ControllerRunHandle) -> Iterator[ControllerEvent]:
        ...

    def interrupt(self, session_id: str) -> None:
        ...


class StaticController:
    def __init__(
        self,
        script: Callable[[ControllerStartRequest | ControllerResumeRequest], list[ControllerEvent]],
    ) -> None:
        self._script = script
        self._handles: dict[str, ControllerRunHandle] = {}

    def start(self, request: ControllerStartRequest) -> ControllerRunHandle:
        session_id = request.session_id or str(uuid4())
        handle = ControllerRunHandle(session_id=session_id, events=list(self._script(request)))
        self._handles[session_id] = handle
        return handle

    def resume(self, request: ControllerResumeRequest) -> ControllerRunHandle:
        session_id = request.session_id or str(uuid4())
        handle = self._handles.get(session_id)
        if handle is None:
            handle = ControllerRunHandle(session_id=session_id, events=list(self._script(request)))
            self._handles[session_id] = handle
        return handle

    def stream(self, handle: ControllerRunHandle) -> Iterator[ControllerEvent]:
        yield from handle.events

    def interrupt(self, session_id: str) -> None:
        self._handles.pop(session_id, None)
