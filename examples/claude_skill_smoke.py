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
            "Read the JSON payload carefully, including any loaded skill content. "
            "Keep the final answer concise."
        ),
    )

    graph = AgentGraph(name="claude-skill-smoke")
    graph.add_operator("claude_real", operator)
    graph.add_node(
        "skill_check",
        operator="claude_real",
        role="researcher",
        objective=(
            "From the loaded skill content, count the numbered workflow steps in the "
            "research-paper-search skill and reply with exactly: FIVE STEPS"
        ),
        skills=["research-paper-search"],
        metadata={"tool_policy": {"mode": "dontAsk", "allowed_tools": []}},
    )

    result = graph.compile().invoke({"task": "real claude skill smoke"}, max_steps=5)

    print("status=", result.status)
    print("completed_nodes=", result.completed_nodes)
    print("messages=")
    for message in result.messages:
        print(message.kind, message.payload)
    print("artifacts=", len(result.artifacts))


if __name__ == "__main__":
    main()
