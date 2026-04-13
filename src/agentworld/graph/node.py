from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

StateSelector = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(slots=True)
class GraphNode:
    name: str
    kind: str = "operator"
    operator_id: str | None = None
    entry: bool | None = None
    objective: str | None = None
    role: str | None = None
    input_selector: StateSelector | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
