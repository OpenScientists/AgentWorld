from __future__ import annotations

import unittest

from agentworld import AgentGraph, DefaultOperator, StaticController
from agentworld.controller.base import ControllerEvent


def noop_controller():
    return StaticController(lambda _request: [ControllerEvent(kind="completed", payload={"state_patch": {}})])


class BuilderValidationTests(unittest.TestCase):
    def test_compile_requires_known_operator(self) -> None:
        graph = AgentGraph(name="invalid")
        graph.add_node("plan", operator="missing")
        with self.assertRaisesRegex(ValueError, "Unknown operator"):
            graph.compile()

    def test_compile_rejects_unknown_conditional_destination(self) -> None:
        graph = AgentGraph(name="invalid-route")
        graph.add_operator("planner", DefaultOperator("planner", noop_controller()))
        graph.add_node("plan", operator="planner")
        graph.add_conditional_edges("plan", lambda state, result: "missing", destinations=["missing"])
        with self.assertRaisesRegex(ValueError, "Unknown conditional edge destination node"):
            graph.compile()


if __name__ == "__main__":
    unittest.main()
