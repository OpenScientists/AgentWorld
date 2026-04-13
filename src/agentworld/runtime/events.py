from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..utils import utc_now


@dataclass(slots=True)
class RunEvent:
    kind: str
    node_name: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
