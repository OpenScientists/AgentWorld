from __future__ import annotations

from .base import AgentController, ControllerResumeRequest, ControllerRunHandle, ControllerStartRequest


class OpenClawController(AgentController):
    def __init__(self, command: str = "openclaw") -> None:
        self.command = command

    def start(self, request: ControllerStartRequest) -> ControllerRunHandle:
        raise NotImplementedError("OpenClawController is not implemented yet.")

    def resume(self, request: ControllerResumeRequest) -> ControllerRunHandle:
        raise NotImplementedError("OpenClawController is not implemented yet.")

    def stream(self, handle: ControllerRunHandle):
        raise NotImplementedError("OpenClawController is not implemented yet.")

    def interrupt(self, session_id: str) -> None:
        raise NotImplementedError("OpenClawController is not implemented yet.")
