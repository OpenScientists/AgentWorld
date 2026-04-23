from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ArtifactRequirement:
    relative_path: str
    description: str = ""
    required: bool = True


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    category: str
    relative_path: str
    suffix: str
    size_bytes: int
    filename: str = ""
    updated_at: str = ""
    schema: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def rel_path(self) -> str:
        return self.relative_path

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "rel_path": self.relative_path,
            "relative_path": self.relative_path,
            "filename": self.filename,
            "suffix": self.suffix,
            "size_bytes": self.size_bytes,
            "updated_at": self.updated_at,
            "schema": dict(self.schema),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArtifactRecord":
        relative_path = str(payload.get("relative_path") or payload.get("rel_path") or "")
        return cls(
            category=str(payload.get("category") or ""),
            relative_path=relative_path,
            suffix=str(payload.get("suffix") or ""),
            size_bytes=int(payload.get("size_bytes") or 0),
            filename=str(payload.get("filename") or Path(relative_path).name),
            updated_at=str(payload.get("updated_at") or ""),
            schema=dict(payload.get("schema") or {}),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class ArtifactIndex:
    generated_at: str
    artifacts: tuple[ArtifactRecord, ...] = ()

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    def to_dict(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for artifact in self.artifacts:
            counts[artifact.category] = counts.get(artifact.category, 0) + 1
        return {
            "generated_at": self.generated_at,
            "artifact_count": self.artifact_count,
            "counts_by_category": counts,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArtifactIndex":
        return cls(
            generated_at=str(payload.get("generated_at") or ""),
            artifacts=tuple(
                ArtifactRecord.from_dict(item)
                for item in payload.get("artifacts", [])
                if isinstance(item, dict)
            ),
        )


@dataclass(frozen=True, slots=True)
class ArtifactValidationResult:
    ok: bool
    missing: tuple[str, ...] = ()
    present: tuple[str, ...] = ()

    @property
    def errors(self) -> list[str]:
        return [f"Missing required artifact: {path}" for path in self.missing]


def resolve_requirement(root: Path, requirement: ArtifactRequirement) -> Path:
    return root / requirement.relative_path
