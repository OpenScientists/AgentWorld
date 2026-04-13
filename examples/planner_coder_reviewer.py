from __future__ import annotations

import json

from agentworld import AgentGraph, DefaultOperator, StaticController
from agentworld.controller.base import ControllerEvent
from agentworld.graph.reducers import append_list


def planner_script(_request):
    return [
        ControllerEvent(
            kind="message_completed",
            payload={
                "kind": "plan",
                "text": "Break the work into implementation and review steps.",
            },
        ),
        ControllerEvent(
            kind="completed",
            payload={
                "state_patch": {
                    "steps": ["implement core package", "review graph result"],
                    "status_log": ["planner completed"],
                }
            },
        ),
    ]


def coder_script(request):
    return [
        ControllerEvent(
            kind="message_completed",
            payload={
                "kind": "observation",
                "text": f"Coder received {len(request.metadata)} metadata keys and produced a draft.",
            },
        ),
        ControllerEvent(
            kind="artifact_created",
            payload={
                "kind": "note",
                "path": "artifacts/draft.txt",
                "description": "Mock draft produced by coder.",
            },
        ),
        ControllerEvent(
            kind="completed",
            payload={
                "state_patch": {
                    "draft_ready": True,
                    "status_log": ["coder completed"],
                }
            },
        ),
    ]


def reviewer_script(_request):
    return [
        ControllerEvent(
            kind="message_completed",
            payload={
                "kind": "review",
                "text": "Draft looks consistent with the plan.",
            },
        ),
        ControllerEvent(
            kind="completed",
            payload={
                "state_patch": {
                    "review_passed": True,
                    "status_log": ["reviewer completed"],
                }
            },
        ),
    ]


def main() -> None:
    graph = AgentGraph(reducers={"steps": append_list, "status_log": append_list}, name="planner-coder-reviewer")
    graph.add_operator("planner_op", DefaultOperator("planner_op", StaticController(planner_script), role="planner"))
    graph.add_operator("coder_op", DefaultOperator("coder_op", StaticController(coder_script), role="coder"))
    graph.add_operator("reviewer_op", DefaultOperator("reviewer_op", StaticController(reviewer_script), role="reviewer"))

    graph.add_node("plan", operator="planner_op", objective="Plan the work")
    graph.add_node("implement", operator="coder_op", objective="Implement the work")
    graph.add_node("review", operator="reviewer_op", objective="Review the work")
    graph.add_edge("plan", "implement")
    graph.add_edge("implement", "review")

    result = graph.compile().invoke({"task": "Start the MAS implementation"})
    print(json.dumps(result.state, indent=2, ensure_ascii=True))
    print(f"messages={len(result.messages)} artifacts={len(result.artifacts)} status={result.status}")


if __name__ == "__main__":
    main()
