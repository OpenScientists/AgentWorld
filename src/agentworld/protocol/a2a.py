from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ..utils import utc_now
from .artifacts import Artifact


@dataclass(slots=True)
class A2AEnvelope:
    thread_id: str
    sender: str
    receiver: str | None
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)
    reply_to: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "kind": self.kind,
            "payload": dict(self.payload),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "reply_to": self.reply_to,
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class Handoff:
    target_node: str
    task: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_envelope(self, *, thread_id: str, sender: str) -> A2AEnvelope:
        return A2AEnvelope(
            thread_id=thread_id,
            sender=sender,
            receiver=self.target_node,
            kind="handoff",
            payload={"task": self.task, **self.payload},
            created_at=self.created_at,
        )
