from __future__ import annotations

from agentworld import AgentGraph, DefaultOperator
from agentworld.controller.claude_code import ClaudeCodeController


def main() -> None:
    controller = ClaudeCodeController(permission_mode="dontAsk")
    operator = DefaultOperator(
        "claude_real",
        controller,
        instruction_prefix=(
            "You are running inside AgentWorld. "
            "Read the JSON payload and complete the objective exactly. "
            "Keep the final answer concise."
        ),
    )

    graph = AgentGraph(name="claude-real-smoke")
    graph.add_operator("claude_real", operator)
    graph.add_node(
        "plan",
        operator="claude_real",
        role="planner",
        objective="Use the Read tool to inspect README.md and reply with exactly: PLAN READY",
        metadata={"tool_policy": {"mode": "dontAsk", "allowed_tools": ["Read"]}},
    )
    graph.add_node(
        "review",
        operator="claude_real",
        role="reviewer",
        objective="Look at the inbox and reply with exactly: REVIEW READY",
        metadata={"tool_policy": {"mode": "dontAsk", "allowed_tools": []}},
    )
    graph.add_edge("plan", "review")

    result = graph.compile().invoke({"task": "real claude smoke"}, max_steps=10)

    print("status=", result.status)
    print("completed_nodes=", result.completed_nodes)
    print("messages=")
    for message in result.messages:
        print(message.kind, message.payload)
    print("artifacts=", len(result.artifacts))


if __name__ == "__main__":
    main()
