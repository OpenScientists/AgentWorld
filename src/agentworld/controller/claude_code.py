from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .base import (
    AgentController,
    ControllerEvent,
    ControllerResumeRequest,
    ControllerRunHandle,
    ControllerStartRequest,
)


class ClaudeCodeController(AgentController):
    def __init__(
        self,
        command: str = "claude",
        *,
        model: str | None = None,
        output_format: str = "stream-json",
        permission_mode: str = "default",
    ) -> None:
        self.command = command
        self.model = model
        self.output_format = output_format
        self.permission_mode = permission_mode

    def start(self, request: ControllerStartRequest) -> ControllerRunHandle:
        session_id = request.session_id or str(uuid4())
        command = self._build_command(request, session_id=session_id, resume=False)
        return self._run_command(command, request, session_id=session_id)

    def resume(self, request: ControllerResumeRequest) -> ControllerRunHandle:
        session_id = request.session_id or str(uuid4())
        command = self._build_command(request, session_id=session_id, resume=True)
        return self._run_command(command, request, session_id=session_id)

    def stream(self, handle: ControllerRunHandle):
        yield from handle.events

    def interrupt(self, session_id: str) -> None:
        return None

    def _build_command(
        self,
        request: ControllerStartRequest | ControllerResumeRequest,
        *,
        session_id: str,
        resume: bool,
    ) -> list[str]:
        if shutil.which(self.command) is None:
            raise FileNotFoundError(f"Claude Code CLI not found: {self.command}")

        command = [
            self.command,
            "-p",
            "--output-format",
            self.output_format,
            "--verbose",
        ]

        if self.model:
            command.extend(["--model", self.model])

        permission_mode = self._resolve_permission_mode(request.tool_policy)
        command.extend(["--permission-mode", permission_mode])

        tools = list(request.tool_policy.get("allowed_tools", []))
        if tools:
            command.extend(["--tools", ",".join(tools)])

        if resume:
            command.extend(["--resume", session_id])
        else:
            command.extend(["--session-id", session_id])

        command.append(request.instruction)
        return command

    def _run_command(
        self,
        command: list[str],
        request: ControllerStartRequest | ControllerResumeRequest,
        *,
        session_id: str,
    ) -> ControllerRunHandle:
        cwd = str(request.working_dir or Path.cwd())
        env = os.environ.copy()
        env.update(request.env)

        raw_stdout = ""
        raw_stderr = ""
        events: list[ControllerEvent] = []

        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=request.timeout_s,
                check=False,
            )
            raw_stdout = completed.stdout or ""
            raw_stderr = completed.stderr or ""
            events.extend(self._parse_stream_output(raw_stdout.splitlines()))
            if completed.returncode != 0 and not any(event.kind == "failed" for event in events):
                events.append(
                    ControllerEvent(
                        kind="failed",
                        payload={
                            "code": f"exit_{completed.returncode}",
                            "message": raw_stderr.strip() or raw_stdout.strip() or "Claude command failed.",
                            "details": {"command": command, "returncode": completed.returncode},
                        },
                    )
                )
        except subprocess.TimeoutExpired as exc:
            raw_stdout = exc.stdout or ""
            raw_stderr = exc.stderr or ""
            events.extend(self._parse_stream_output(raw_stdout.splitlines()))
            events.append(
                ControllerEvent(
                    kind="failed",
                    payload={
                        "code": "timeout",
                        "message": f"Claude command timed out after {request.timeout_s} seconds.",
                        "details": {"command": command, "timeout_s": request.timeout_s},
                    },
                )
            )

        return ControllerRunHandle(
            session_id=session_id,
            events=events,
            metadata={
                "command": command,
                "cwd": cwd,
                "stdout": raw_stdout,
                "stderr": raw_stderr,
            },
        )

    def _parse_stream_output(self, lines: Iterable[str]) -> list[ControllerEvent]:
        events: list[ControllerEvent] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                events.append(
                    ControllerEvent(
                        kind="failed",
                        payload={
                            "code": "invalid_json_line",
                            "message": "Claude returned a non-JSON line while using stream-json mode.",
                            "details": {"line": line},
                        },
                    )
                )
                continue

            record_type = payload.get("type")
            if record_type == "system" and payload.get("subtype") == "init":
                events.append(
                    ControllerEvent(
                        kind="session_started",
                        payload={
                            "session_id": payload.get("session_id"),
                            "model": payload.get("model"),
                            "tools": payload.get("tools", []),
                            "permission_mode": payload.get("permissionMode"),
                        },
                    )
                )
                continue

            if record_type == "assistant":
                events.extend(self._parse_assistant_message(payload))
                continue

            if record_type == "user":
                events.extend(self._parse_user_message(payload))
                continue

            if record_type == "result":
                if payload.get("is_error"):
                    events.append(
                        ControllerEvent(
                            kind="failed",
                            payload={
                                "code": "result_error",
                                "message": str(payload.get("result", "Claude returned an error result.")),
                                "details": payload,
                            },
                        )
                    )
                else:
                    events.append(
                        ControllerEvent(
                            kind="completed",
                            payload={
                                "result": payload.get("result"),
                                "usage": payload.get("usage", {}),
                                "duration_ms": payload.get("duration_ms"),
                                "trace_ref": payload.get("session_id"),
                                "status": "success",
                            },
                        )
                    )
                continue

        return events

    def _parse_assistant_message(self, payload: dict[str, Any]) -> list[ControllerEvent]:
        events: list[ControllerEvent] = []
        message = payload.get("message", {})
        created_at = payload.get("created_at")
        for block in message.get("content", []):
            block_type = block.get("type")
            if block_type == "text":
                events.append(
                    ControllerEvent(
                        kind="message_completed",
                        payload={"kind": "observation", "text": block.get("text", "")},
                    )
                )
            elif block_type == "tool_use":
                events.append(
                    ControllerEvent(
                        kind="tool_call",
                        payload={
                            "id": block.get("id"),
                            "name": block.get("name"),
                            "input": block.get("input", {}),
                        },
                    )
                )
        return events

    def _parse_user_message(self, payload: dict[str, Any]) -> list[ControllerEvent]:
        events: list[ControllerEvent] = []
        message = payload.get("message", {})
        for block in message.get("content", []):
            if block.get("type") != "tool_result":
                continue
            events.append(
                ControllerEvent(
                    kind="tool_result",
                    payload={
                        "tool_use_id": block.get("tool_use_id"),
                        "content": block.get("content"),
                    },
                )
            )
        return events

    def _resolve_permission_mode(self, tool_policy: dict[str, Any]) -> str:
        valid_modes = {"acceptEdits", "bypassPermissions", "default", "dontAsk", "plan", "auto"}
        explicit = tool_policy.get("permissions", {}).get("permission_mode")
        if explicit in valid_modes:
            return explicit
        mode = tool_policy.get("mode")
        if mode in valid_modes:
            return str(mode)
        return self.permission_mode
