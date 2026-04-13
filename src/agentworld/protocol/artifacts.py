from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ..utils import utc_now


@dataclass(slots=True)
class Artifact:
    kind: str
    path: str | None = None
    uri: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "uri": self.uri,
            "description": self.description,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }
