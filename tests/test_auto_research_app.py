from __future__ import annotations

import unittest

from agentworld.apps.auto_research import create_auto_research_app
from agentworld.approval import AutoApproveGate, TerminalApprovalGate
from agentworld.stage import ControllerStageOperator


class AutoResearchAppTests(unittest.TestCase):
    def test_create_auto_research_app_builds_real_controller_stack(self) -> None:
        app = create_auto_research_app(
            approval_mode="validation-only",
            model="sonnet",
            claude_command="claude",
            permission_mode="default",
        )

        self.assertEqual(app.config.backend, "claude-code")
        self.assertEqual(app.config.approval_mode, "validation-only")
        self.assertIsInstance(app.workflow.operator, ControllerStageOperator)
        self.assertIsInstance(app.workflow.approval_gate, AutoApproveGate)

    def test_manual_approval_uses_terminal_gate(self) -> None:
        app = create_auto_research_app(approval_mode="manual")

        self.assertIsInstance(app.workflow.approval_gate, TerminalApprovalGate)


if __name__ == "__main__":
    unittest.main()
