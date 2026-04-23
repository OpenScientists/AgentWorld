from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
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
        if handle.metadata.get("_completed"):
            yield from handle.events
            return
        if "command" not in handle.metadata:
            yield from handle.events
            return
        yield from self._stream_command(handle)

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

        return ControllerRunHandle(
            session_id=session_id,
            events=[],
            metadata={
                "command": command,
                "cwd": cwd,
                "env_updates": dict(request.env),
                "timeout_s": request.timeout_s,
                "stdout": "",
                "stderr": "",
                "_completed": False,
            },
        )

    def _stream_command(self, handle: ControllerRunHandle):
        command = [str(item) for item in handle.metadata["command"]]
        cwd = str(handle.metadata.get("cwd") or Path.cwd())
        env = os.environ.copy()
        env.update(dict(handle.metadata.get("env_updates", {})))
        timeout_s = handle.metadata.get("timeout_s")
        raw_lines: list[str] = []
        emitted: list[ControllerEvent] = []
        timed_out = threading.Event()
        start_time = time.monotonic()

        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            event = ControllerEvent(
                kind="failed",
                payload={
                    "code": "spawn_failed",
                    "message": str(exc),
                    "details": {"command": command, "cwd": cwd},
                },
            )
            handle.events.append(event)
            handle.metadata["_completed"] = True
            yield event
            return

        if process.stdout is None:
            event = ControllerEvent(
                kind="failed",
                payload={
                    "code": "stdout_unavailable",
                    "message": "Failed to capture Claude Code output stream.",
                    "details": {"command": command, "cwd": cwd},
                },
            )
            handle.events.append(event)
            handle.metadata["_completed"] = True
            yield event
            return

        def _on_timeout() -> None:
            timed_out.set()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        timer: threading.Timer | None = None
        if isinstance(timeout_s, (int, float)) and timeout_s > 0:
            timer = threading.Timer(float(timeout_s), _on_timeout)
            timer.daemon = True
            timer.start()

        try:
            for raw_line in process.stdout:
                if timed_out.is_set():
                    break
                line = raw_line.rstrip("\n")
                raw_lines.append(line)
                events = self._parse_stream_output([line])
                emitted.extend(events)
                for event in events:
                    handle.events.append(event)
                    yield event
        finally:
            if timer is not None:
                timer.cancel()
            process.stdout.close()

        exit_code = process.wait()
        raw_stdout = "\n".join(raw_lines)
        handle.metadata["stdout"] = raw_stdout
        handle.metadata["stderr"] = ""
        handle.metadata["returncode"] = exit_code
        handle.metadata["duration_s"] = round(time.monotonic() - start_time, 3)
        handle.metadata["_completed"] = True

        if timed_out.is_set():
            event = ControllerEvent(
                kind="failed",
                payload={
                    "code": "timeout",
                    "message": f"Claude command timed out after {timeout_s} seconds.",
                    "details": {"command": command, "timeout_s": timeout_s},
                },
            )
            handle.events.append(event)
            yield event
            return

        if exit_code != 0 and not any(event.kind == "failed" for event in emitted):
            event = ControllerEvent(
                kind="failed",
                payload={
                    "code": f"exit_{exit_code}",
                    "message": raw_stdout.strip() or "Claude command failed.",
                    "details": {"command": command, "returncode": exit_code},
                },
            )
            handle.events.append(event)
            yield event

    def _parse_stream_output(self, lines: Iterable[str]) -> list[ControllerEvent]:
        events: list[ControllerEvent] = []
        for line in lines:
            line = _strip_ansi(line).strip()
            if not line:
                continue

            try:
                payload = _clean_json_value(json.loads(line))
            except json.JSONDecodeError:
                events.append(
                    ControllerEvent(
                        kind="log",
                        payload={
                            "stream": "stdout",
                            "text": line,
                        },
                    )
                )
                continue
            if not isinstance(payload, dict):
                events.append(ControllerEvent(kind="log", payload={"stream": "stdout", "text": str(payload)}))
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


ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(value: str) -> str:
    return ANSI_PATTERN.sub("", value)


def _clean_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return _strip_ansi(value)
    if isinstance(value, list):
        return [_clean_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean_json_value(item) for key, item in value.items()}
    return value
