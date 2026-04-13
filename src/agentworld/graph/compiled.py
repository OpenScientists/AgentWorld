from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..protocol.a2a import A2AEnvelope
from ..protocol.artifacts import Artifact
from ..runtime.events import RunEvent


@dataclass(slots=True)
class GraphRunResult:
    graph_id: str
    run_id: str
    thread_id: str
    state: dict[str, Any]
    messages: list[A2AEnvelope] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    trace: list[RunEvent] = field(default_factory=list)
    completed_nodes: list[str] = field(default_factory=list)
    status: str = "success"
    error: str | None = None


class CompiledGraph:
    def __init__(
        self,
        *,
        graph_id: str,
        state_schema: type | None,
        context_schema: type | None,
        nodes: dict[str, Any],
        operators: dict[str, Any],
        edges: dict[str, list[str]],
        waiting_edges: list[Any],
        conditional_edges: dict[str, Any],
        reducers: dict[str, Any],
    ) -> None:
        self.graph_id = graph_id
        self.state_schema = state_schema
        self.context_schema = context_schema
        self.nodes = nodes
        self.operators = operators
        self.edges = edges
        self.waiting_edges = waiting_edges
        self.conditional_edges = conditional_edges
        self.reducers = reducers

    def invoke(
        self,
        input_state: Mapping[str, Any] | None = None,
        *,
        context: Mapping[str, Any] | None = None,
        working_dir: str | Path | None = None,
        max_steps: int = 100,
    ) -> GraphRunResult:
        from ..runtime.executor import GraphExecutor

        executor = GraphExecutor(self)
        return executor.invoke(
            input_state=dict(input_state or {}),
            context=dict(context or {}),
            working_dir=Path(working_dir) if working_dir is not None else None,
            max_steps=max_steps,
        )
