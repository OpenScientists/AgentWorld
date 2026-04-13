from __future__ import annotations

import inspect
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from ..operator.models import OperatorRequest, RuntimeContext, ToolPolicy
from ..protocol.a2a import A2AEnvelope
from ..runtime.events import RunEvent
from ..utils import utc_now
from ..graph.compiled import GraphRunResult
from ..graph.reducers import merge_state


class GraphExecutor:
    def __init__(self, graph) -> None:
        self.graph = graph

    def invoke(
        self,
        *,
        input_state: dict[str, Any],
        context: Mapping[str, Any],
        working_dir: Path | None,
        max_steps: int,
    ) -> GraphRunResult:
        run_id = str(uuid4())
        thread_id = str(uuid4())
        cwd = working_dir or Path.cwd()
        state = dict(input_state)
        global_messages: list[A2AEnvelope] = []
        artifacts = []
        trace: list[RunEvent] = []
        completed_nodes: list[str] = []
        queue = deque(self._entry_nodes())
        inboxes: dict[str, list[A2AEnvelope]] = defaultdict(list)
        join_progress: dict[tuple[tuple[str, ...], str], set[str]] = {}
        join_messages: dict[tuple[tuple[str, ...], str], list[A2AEnvelope]] = defaultdict(list)

        if not queue:
            raise ValueError("Graph has no entry nodes.")

        steps = 0
        while queue:
            steps += 1
            if steps > max_steps:
                trace.append(RunEvent(kind="graph_timeout", payload={"max_steps": max_steps}))
                return GraphRunResult(
                    graph_id=self.graph.graph_id,
                    run_id=run_id,
                    thread_id=thread_id,
                    state=state,
                    messages=global_messages,
                    artifacts=artifacts,
                    trace=trace,
                    completed_nodes=completed_nodes,
                    status="timeout",
                    error=f"Graph exceeded max_steps={max_steps}.",
                )

            node_name = queue.popleft()
            node = self.graph.nodes[node_name]
            operator = self.graph.operators[node.operator_id]
            trace.append(RunEvent(kind="node_started", node_name=node_name))

            state_view = dict(node.input_selector(state) if node.input_selector else state)
            raw_tool_policy = node.metadata.get("tool_policy")
            if isinstance(raw_tool_policy, ToolPolicy):
                tool_policy = raw_tool_policy
            elif isinstance(raw_tool_policy, dict):
                tool_policy = ToolPolicy(
                    mode=str(raw_tool_policy.get("mode", "inherit")),
                    allowed_tools=list(raw_tool_policy.get("allowed_tools", [])),
                    permissions=dict(raw_tool_policy.get("permissions", {})),
                )
            else:
                tool_policy = ToolPolicy()
            request = OperatorRequest(
                operator_id=node.operator_id or node_name,
                role=node.role or node_name,
                objective=node.objective or f"Execute node {node_name}",
                state_view=state_view,
                inbox=list(inboxes.pop(node_name, [])),
                artifacts=list(artifacts),
                working_dir=cwd,
                tool_policy=tool_policy,
                metadata={"graph_id": self.graph.graph_id, "node_name": node_name},
            )
            runtime = RuntimeContext(
                graph_id=self.graph.graph_id,
                run_id=run_id,
                thread_id=thread_id,
                node_name=node_name,
                context=context,
                working_dir=cwd,
                metadata=node.metadata,
            )
            result = operator.invoke(request, runtime)

            state = merge_state(state, result.state_patch, self.graph.reducers)
            global_messages.extend(result.messages)
            artifacts.extend(result.artifacts)
            completed_nodes.append(node_name)
            trace.append(
                RunEvent(
                    kind="node_completed",
                    node_name=node_name,
                    payload={"status": result.status, "state_patch": dict(result.state_patch)},
                )
            )

            if not result.is_success:
                return GraphRunResult(
                    graph_id=self.graph.graph_id,
                    run_id=run_id,
                    thread_id=thread_id,
                    state=state,
                    messages=global_messages,
                    artifacts=artifacts,
                    trace=trace,
                    completed_nodes=completed_nodes,
                    status=result.status,
                    error=result.error.message if result.error else "Operator failed.",
                )

            direct_targets = list(self.graph.edges.get(node_name, []))
            conditional_targets = self._resolve_targets(node_name, state, result)
            scheduled_targets = self._unique_targets(direct_targets + conditional_targets)

            for handoff in result.handoffs:
                envelope = handoff.to_envelope(thread_id=thread_id, sender=node_name)
                inboxes[handoff.target_node].append(envelope)
                if handoff.target_node not in scheduled_targets:
                    scheduled_targets.append(handoff.target_node)

            shared_messages = [message for message in result.messages if message.receiver is None]
            for target in scheduled_targets:
                inboxes[target].extend(shared_messages)
                inboxes[target].extend([message for message in result.messages if message.receiver == target])
                queue.append(target)

            for edge in self.graph.waiting_edges:
                if node_name not in edge.starts:
                    continue
                key = (edge.starts, edge.end)
                seen = join_progress.setdefault(key, set())
                seen.add(node_name)
                join_messages[key].extend(shared_messages)
                if seen == set(edge.starts):
                    inboxes[edge.end].extend(join_messages.pop(key, []))
                    queue.append(edge.end)

        trace.append(RunEvent(kind="graph_completed", payload={"completed_nodes": list(completed_nodes)}))
        return GraphRunResult(
            graph_id=self.graph.graph_id,
            run_id=run_id,
            thread_id=thread_id,
            state=state,
            messages=global_messages,
            artifacts=artifacts,
            trace=trace,
            completed_nodes=completed_nodes,
        )

    def _entry_nodes(self) -> list[str]:
        incoming: dict[str, int] = {name: 0 for name in self.graph.nodes}
        for start, ends in self.graph.edges.items():
            for end in ends:
                incoming[end] += 1
        for edge in self.graph.waiting_edges:
            incoming[edge.end] += len(edge.starts)
        for route in self.graph.conditional_edges.values():
            for destination in route.destinations:
                incoming[destination] += 1
        entries: list[str] = []
        for name, degree in incoming.items():
            node = self.graph.nodes[name]
            if node.entry is True:
                entries.append(name)
            elif node.entry is False:
                continue
            elif degree == 0:
                entries.append(name)
        return entries

    def _resolve_targets(self, node_name: str, state: Mapping[str, Any], result) -> list[str]:
        route = self.graph.conditional_edges.get(node_name)
        if route is None:
            return []
        signature = inspect.signature(route.path)
        if len(signature.parameters) == 1:
            raw = route.path(state)
        else:
            raw = route.path(state, result)
        if raw is None:
            return []
        if isinstance(raw, str):
            return [raw]
        return [str(item) for item in raw]

    def _unique_targets(self, targets: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for target in targets:
            if target in seen:
                continue
            seen.add(target)
            ordered.append(target)
        return ordered
