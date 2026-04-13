from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from ..operator.base import Operator
from ..operator.models import OperatorResult
from .compiled import CompiledGraph
from .edge import WaitingEdge
from .node import GraphNode, StateSelector
from .reducers import Reducer

RouteFn = Callable[[Mapping[str, Any], OperatorResult], str | Sequence[str] | None]


@dataclass(slots=True)
class ConditionalRoute:
    path: RouteFn
    destinations: tuple[str, ...] = ()


class AgentGraph:
    def __init__(
        self,
        *,
        state_schema: type | None = None,
        context_schema: type | None = None,
        reducers: dict[str, Reducer] | None = None,
        name: str = "AgentGraph",
    ) -> None:
        self.state_schema = state_schema
        self.context_schema = context_schema
        self.reducers = dict(reducers or {})
        self.name = name
        self.nodes: dict[str, GraphNode] = {}
        self.operators: dict[str, Operator] = {}
        self.edges: dict[str, list[str]] = defaultdict(list)
        self.waiting_edges: list[WaitingEdge] = []
        self.conditional_edges: dict[str, ConditionalRoute] = {}

    def add_operator(self, name: str, operator: Operator) -> "AgentGraph":
        if name in self.operators:
            raise ValueError(f"Operator already exists: {name}")
        self.operators[name] = operator
        return self

    def add_node(
        self,
        name: str,
        *,
        operator: str | None = None,
        kind: str = "operator",
        entry: bool | None = None,
        objective: str | None = None,
        role: str | None = None,
        input_selector: StateSelector | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AgentGraph":
        if name in self.nodes:
            raise ValueError(f"Node already exists: {name}")
        self.nodes[name] = GraphNode(
            name=name,
            kind=kind,
            operator_id=operator,
            entry=entry,
            objective=objective,
            role=role,
            input_selector=input_selector,
            metadata=dict(metadata or {}),
        )
        return self

    def add_edge(self, start_key: str | Sequence[str], end_key: str) -> "AgentGraph":
        if isinstance(start_key, str):
            self.edges[start_key].append(end_key)
        else:
            starts = tuple(start_key)
            if not starts:
                raise ValueError("Waiting edge requires at least one start node.")
            self.waiting_edges.append(WaitingEdge(starts=starts, end=end_key))
        return self

    def add_conditional_edges(
        self,
        source: str,
        path: RouteFn,
        *,
        destinations: Sequence[str] | None = None,
    ) -> "AgentGraph":
        self.conditional_edges[source] = ConditionalRoute(
            path=path,
            destinations=tuple(destinations or ()),
        )
        return self

    def compile(self) -> CompiledGraph:
        self.validate()
        return CompiledGraph(
            graph_id=self.name,
            state_schema=self.state_schema,
            context_schema=self.context_schema,
            nodes=dict(self.nodes),
            operators=dict(self.operators),
            edges={key: list(value) for key, value in self.edges.items()},
            waiting_edges=list(self.waiting_edges),
            conditional_edges=dict(self.conditional_edges),
            reducers=dict(self.reducers),
        )

    def validate(self) -> None:
        if not self.nodes:
            raise ValueError("Graph must have at least one node.")

        for name, node in self.nodes.items():
            if node.kind == "operator":
                if not node.operator_id:
                    raise ValueError(f"Operator node {name} is missing operator_id.")
                if node.operator_id not in self.operators:
                    raise ValueError(f"Unknown operator for node {name}: {node.operator_id}")

        for start, ends in self.edges.items():
            if start not in self.nodes:
                raise ValueError(f"Unknown edge start node: {start}")
            for end in ends:
                if end not in self.nodes:
                    raise ValueError(f"Unknown edge end node: {end}")

        for edge in self.waiting_edges:
            for start in edge.starts:
                if start not in self.nodes:
                    raise ValueError(f"Unknown waiting edge start node: {start}")
            if edge.end not in self.nodes:
                raise ValueError(f"Unknown waiting edge end node: {edge.end}")

        for source, route in self.conditional_edges.items():
            if source not in self.nodes:
                raise ValueError(f"Unknown conditional edge source node: {source}")
            for destination in route.destinations:
                if destination not in self.nodes:
                    raise ValueError(f"Unknown conditional edge destination node: {destination}")
