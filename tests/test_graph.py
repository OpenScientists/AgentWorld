from __future__ import annotations

import json
import unittest

from agentworld import AgentGraph, DefaultOperator, StaticController, append_list
from agentworld.controller.base import ControllerEvent


def controller_from_script(script):
    return StaticController(script)


class AgentGraphTests(unittest.TestCase):
    def test_sequential_graph_merges_state_messages_and_artifacts(self) -> None:
        def planner(_request):
            return [
                ControllerEvent(
                    kind="message_completed",
                    payload={"kind": "plan", "text": "Split the task into code and review."},
                ),
                ControllerEvent(
                    kind="completed",
                    payload={
                        "state_patch": {
                            "steps": ["implement core", "review output"],
                            "status_log": ["planner completed"],
                        }
                    },
                ),
            ]

        def coder(_request):
            return [
                ControllerEvent(
                    kind="artifact_created",
                    payload={"kind": "note", "path": "artifacts/draft.txt"},
                ),
                ControllerEvent(
                    kind="message_completed",
                    payload={"kind": "observation", "text": "Draft is ready."},
                ),
                ControllerEvent(
                    kind="completed",
                    payload={"state_patch": {"draft_ready": True, "status_log": ["coder completed"]}},
                ),
            ]

        def reviewer(_request):
            return [
                ControllerEvent(
                    kind="message_completed",
                    payload={"kind": "review", "text": "Review passed."},
                ),
                ControllerEvent(
                    kind="completed",
                    payload={"state_patch": {"review_passed": True, "status_log": ["reviewer completed"]}},
                ),
            ]

        graph = AgentGraph(reducers={"steps": append_list, "status_log": append_list}, name="sequential")
        graph.add_operator("planner_op", DefaultOperator("planner_op", controller_from_script(planner)))
        graph.add_operator("coder_op", DefaultOperator("coder_op", controller_from_script(coder)))
        graph.add_operator("reviewer_op", DefaultOperator("reviewer_op", controller_from_script(reviewer)))
        graph.add_node("plan", operator="planner_op")
        graph.add_node("implement", operator="coder_op")
        graph.add_node("review", operator="reviewer_op")
        graph.add_edge("plan", "implement")
        graph.add_edge("implement", "review")

        result = graph.compile().invoke({"task": "Build the MAS"})

        self.assertEqual(result.status, "success")
        self.assertEqual(result.completed_nodes, ["plan", "implement", "review"])
        self.assertEqual(result.state["steps"], ["implement core", "review output"])
        self.assertEqual(
            result.state["status_log"],
            ["planner completed", "coder completed", "reviewer completed"],
        )
        self.assertTrue(result.state["draft_ready"])
        self.assertTrue(result.state["review_passed"])
        self.assertEqual(len(result.messages), 3)
        self.assertEqual(len(result.artifacts), 1)

    def test_conditional_edges_route_to_only_one_destination(self) -> None:
        def make_patch(patch):
            def script(_request):
                return [ControllerEvent(kind="completed", payload={"state_patch": patch})]

            return script

        graph = AgentGraph(name="conditional")
        graph.add_operator("start_op", DefaultOperator("start_op", controller_from_script(make_patch({"route": "right"}))))
        graph.add_operator("left_op", DefaultOperator("left_op", controller_from_script(make_patch({"left": True}))))
        graph.add_operator("right_op", DefaultOperator("right_op", controller_from_script(make_patch({"right": True}))))
        graph.add_node("start", operator="start_op")
        graph.add_node("left", operator="left_op")
        graph.add_node("right", operator="right_op")
        graph.add_conditional_edges("start", lambda state, result: state["route"], destinations=["left", "right"])

        result = graph.compile().invoke({})

        self.assertEqual(result.status, "success")
        self.assertEqual(result.completed_nodes, ["start", "right"])
        self.assertEqual(result.state["route"], "right")
        self.assertTrue(result.state["right"])
        self.assertNotIn("left", result.state)

    def test_join_edge_waits_for_all_predecessors_and_delivers_shared_messages(self) -> None:
        def start(_request):
            return [ControllerEvent(kind="completed", payload={"state_patch": {"started": True}})]

        def worker(name: str):
            def script(_request):
                return [
                    ControllerEvent(kind="message_completed", payload={"kind": "observation", "text": name}),
                    ControllerEvent(kind="completed", payload={"state_patch": {f"{name}_done": True}}),
                ]

            return script

        def join(request):
            payload = json.loads(request.instruction)
            inbox = payload["inbox"]
            return [
                ControllerEvent(
                    kind="completed",
                    payload={
                        "state_patch": {
                            "join_seen": sorted(item["payload"]["text"] for item in inbox),
                            "join_inbox_count": len(inbox),
                        }
                    },
                )
            ]

        graph = AgentGraph(reducers={"join_seen": append_list}, name="join")
        graph.add_operator("start_op", DefaultOperator("start_op", controller_from_script(start)))
        graph.add_operator("a_op", DefaultOperator("a_op", controller_from_script(worker("a"))))
        graph.add_operator("b_op", DefaultOperator("b_op", controller_from_script(worker("b"))))
        graph.add_operator("join_op", DefaultOperator("join_op", controller_from_script(join)))
        graph.add_node("start", operator="start_op")
        graph.add_node("a", operator="a_op")
        graph.add_node("b", operator="b_op")
        graph.add_node("join", operator="join_op")
        graph.add_edge("start", "a")
        graph.add_edge("start", "b")
        graph.add_edge(["a", "b"], "join")

        result = graph.compile().invoke({})

        self.assertEqual(result.status, "success")
        self.assertEqual(result.completed_nodes, ["start", "a", "b", "join"])
        self.assertEqual(result.state["join_inbox_count"], 2)
        self.assertEqual(result.state["join_seen"], ["a", "b"])

    def test_handoff_schedules_target_without_explicit_edge(self) -> None:
        def planner(_request):
            return [
                ControllerEvent(
                    kind="completed",
                    payload={
                        "handoffs": [
                            {
                                "target_node": "review",
                                "task": "Review the generated draft",
                                "payload": {"priority": "high"},
                            }
                        ]
                    },
                )
            ]

        def reviewer(request):
            payload = json.loads(request.instruction)
            inbox = payload["inbox"]
            return [
                ControllerEvent(
                    kind="completed",
                    payload={
                        "state_patch": {
                            "handoff_task": inbox[0]["payload"]["task"],
                            "handoff_priority": inbox[0]["payload"]["priority"],
                        }
                    },
                )
            ]

        graph = AgentGraph(name="handoff")
        graph.add_operator("planner_op", DefaultOperator("planner_op", controller_from_script(planner)))
        graph.add_operator("reviewer_op", DefaultOperator("reviewer_op", controller_from_script(reviewer)))
        graph.add_node("plan", operator="planner_op")
        graph.add_node("review", operator="reviewer_op", entry=False)

        result = graph.compile().invoke({})

        self.assertEqual(result.status, "success")
        self.assertEqual(result.completed_nodes, ["plan", "review"])
        self.assertEqual(result.state["handoff_task"], "Review the generated draft")
        self.assertEqual(result.state["handoff_priority"], "high")

    def test_failed_operator_stops_graph_and_returns_error(self) -> None:
        def fail(_request):
            return [
                ControllerEvent(
                    kind="failed",
                    payload={"code": "boom", "message": "controller failed on purpose"},
                )
            ]

        def next_step(_request):
            return [ControllerEvent(kind="completed", payload={"state_patch": {"should_not_run": True}})]

        graph = AgentGraph(name="failure")
        graph.add_operator("fail_op", DefaultOperator("fail_op", controller_from_script(fail)))
        graph.add_operator("next_op", DefaultOperator("next_op", controller_from_script(next_step)))
        graph.add_node("fail", operator="fail_op")
        graph.add_node("next", operator="next_op")
        graph.add_edge("fail", "next")

        result = graph.compile().invoke({})

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.completed_nodes, ["fail"])
        self.assertEqual(result.error, "controller failed on purpose")
        self.assertNotIn("should_not_run", result.state)


if __name__ == "__main__":
    unittest.main()
