from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from agentworld.controller.base import ControllerStartRequest
from agentworld.controller.claude_code import ClaudeCodeController


class ClaudeCodeControllerTests(unittest.TestCase):
    @patch("agentworld.controller.claude_code.shutil.which", return_value="/usr/bin/claude")
    def test_build_command_for_start(self, _which) -> None:
        controller = ClaudeCodeController(model="sonnet")
        request = ControllerStartRequest(
            instruction="Reply with OK.",
            working_dir=Path.cwd(),
            tool_policy={"mode": "dontAsk", "allowed_tools": ["Read"]},
        )

        command = controller._build_command(request, session_id="00000000-0000-0000-0000-000000000001", resume=False)

        self.assertEqual(command[0], "claude")
        self.assertIn("-p", command)
        self.assertIn("--output-format", command)
        self.assertIn("stream-json", command)
        self.assertIn("--model", command)
        self.assertIn("sonnet", command)
        self.assertIn("--permission-mode", command)
        self.assertIn("dontAsk", command)
        self.assertIn("--tools", command)
        self.assertIn("Read", command)
        self.assertIn("--session-id", command)
        self.assertEqual(command[-1], "Reply with OK.")

    def test_parse_stream_output_emits_session_tool_text_and_result_events(self) -> None:
        controller = ClaudeCodeController()
        lines = [
            json.dumps(
                {
                    "type": "system",
                    "subtype": "init",
                    "session_id": "sess-1",
                    "model": "claude-sonnet",
                    "tools": ["Read"],
                    "permissionMode": "dontAsk",
                }
            ),
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "id": "tool-1", "name": "Read", "input": {"file_path": "README.md"}},
                            {"type": "text", "text": "DONE"},
                        ]
                    },
                }
            ),
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {"type": "tool_result", "tool_use_id": "tool-1", "content": "file contents"},
                        ]
                    },
                }
            ),
            json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": "DONE",
                    "session_id": "sess-1",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                }
            ),
        ]

        events = controller._parse_stream_output(lines)
        kinds = [event.kind for event in events]

        self.assertEqual(kinds, ["session_started", "tool_call", "message_completed", "tool_result", "completed"])
        self.assertEqual(events[1].payload["name"], "Read")
        self.assertEqual(events[2].payload["text"], "DONE")
        self.assertEqual(events[3].payload["tool_use_id"], "tool-1")
        self.assertEqual(events[4].payload["result"], "DONE")


if __name__ == "__main__":
    unittest.main()
