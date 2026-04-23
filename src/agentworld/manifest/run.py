from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..stage import StageSpec
from ..utils import utc_now
from ..workspace import RunWorkspace, relative_to_run


@dataclass(frozen=True, slots=True)
class StageManifestEntry:
    number: int
    slug: str
    title: str
    status: str = "pending"
    approved: bool = False
    dirty: bool = False
    stale: bool = False
    attempt_count: int = 0
    session_id: str | None = None
    final_stage_path: str = ""
    draft_stage_path: str = ""
    artifact_paths: tuple[str, ...] = ()
    last_error: str | None = None
    invalidated_reason: str | None = None
    invalidated_by_stage: str | None = None
    updated_at: str = ""
    approved_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "number": self.number,
            "slug": self.slug,
            "title": self.title,
            "status": self.status,
            "approved": self.approved,
            "dirty": self.dirty,
            "stale": self.stale,
            "attempt_count": self.attempt_count,
            "session_id": self.session_id,
            "final_stage_path": self.final_stage_path,
            "draft_stage_path": self.draft_stage_path,
            "artifact_paths": list(self.artifact_paths),
            "last_error": self.last_error,
            "invalidated_reason": self.invalidated_reason,
            "invalidated_by_stage": self.invalidated_by_stage,
            "updated_at": self.updated_at,
            "approved_at": self.approved_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "StageManifestEntry":
        return cls(
            number=int(payload.get("number") or 0),
            slug=str(payload.get("slug") or ""),
            title=str(payload.get("title") or ""),
            status=str(payload.get("status") or "pending"),
            approved=bool(payload.get("approved", False)),
            dirty=bool(payload.get("dirty", False)),
            stale=bool(payload.get("stale", False)),
            attempt_count=int(payload.get("attempt_count") or 0),
            session_id=str(payload["session_id"]) if payload.get("session_id") is not None else None,
            final_stage_path=str(payload.get("final_stage_path") or ""),
            draft_stage_path=str(payload.get("draft_stage_path") or ""),
            artifact_paths=tuple(str(item) for item in payload.get("artifact_paths", []) if str(item).strip()),
            last_error=str(payload["last_error"]) if payload.get("last_error") is not None else None,
            invalidated_reason=str(payload["invalidated_reason"])
            if payload.get("invalidated_reason") is not None
            else None,
            invalidated_by_stage=str(payload["invalidated_by_stage"])
            if payload.get("invalidated_by_stage") is not None
            else None,
            updated_at=str(payload.get("updated_at") or ""),
            approved_at=str(payload["approved_at"]) if payload.get("approved_at") is not None else None,
        )


@dataclass(frozen=True, slots=True)
class RunManifest:
    run_id: str
    created_at: str
    updated_at: str
    run_status: str
    last_event: str
    current_stage_slug: str | None
    last_error: str | None
    completed_at: str | None
    stages: tuple[StageManifestEntry, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "run_status": self.run_status,
            "last_event": self.last_event,
            "current_stage_slug": self.current_stage_slug,
            "last_error": self.last_error,
            "completed_at": self.completed_at,
            "stages": [stage.to_dict() for stage in self.stages],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "RunManifest":
        stages = payload.get("stages", [])
        return cls(
            run_id=str(payload.get("run_id") or ""),
            created_at=str(payload.get("created_at") or utc_now()),
            updated_at=str(payload.get("updated_at") or utc_now()),
            run_status=str(payload.get("run_status") or "pending"),
            last_event=str(payload.get("last_event") or "run.created"),
            current_stage_slug=str(payload["current_stage_slug"])
            if payload.get("current_stage_slug") is not None
            else None,
            last_error=str(payload["last_error"]) if payload.get("last_error") is not None else None,
            completed_at=str(payload["completed_at"]) if payload.get("completed_at") is not None else None,
            stages=tuple(StageManifestEntry.from_dict(item) for item in stages if isinstance(item, dict)),
        )


def initialize_run_manifest(workspace: RunWorkspace, stages: tuple[StageSpec, ...]) -> RunManifest:
    timestamp = utc_now()
    manifest = RunManifest(
        run_id=workspace.run_root.name,
        created_at=timestamp,
        updated_at=timestamp,
        run_status="pending",
        last_event="run.created",
        current_stage_slug=None,
        last_error=None,
        completed_at=None,
        stages=tuple(
            StageManifestEntry(
                number=stage.number,
                slug=stage.slug,
                title=stage.title,
                final_stage_path=relative_to_run(workspace, workspace.stage_final_path(stage.slug)),
                draft_stage_path=relative_to_run(workspace, workspace.stage_draft_path(stage.slug)),
                updated_at=timestamp,
            )
            for stage in stages
        ),
    )
    save_run_manifest(workspace.run_manifest, manifest)
    return manifest


def ensure_run_manifest(workspace: RunWorkspace, stages: tuple[StageSpec, ...]) -> RunManifest:
    manifest = load_run_manifest(workspace.run_manifest)
    if manifest is not None:
        existing_slugs = {entry.slug for entry in manifest.stages}
        expected_slugs = {stage.slug for stage in stages}
        if expected_slugs.issubset(existing_slugs):
            return manifest
    return initialize_run_manifest(workspace, stages)


def load_run_manifest(path: Path) -> RunManifest | None:
    if not path.exists():
        return None
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return RunManifest.from_dict(json.loads(text))
        except (OSError, json.JSONDecodeError) as exc:
            last_error = exc
        if attempt < 4:
            time.sleep(0.02 * (attempt + 1))
    if last_error is not None:
        raise RuntimeError(f"Failed to read run manifest at {path}: {last_error}") from last_error
    return None


def save_run_manifest(path: Path, manifest: RunManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest.to_dict(), indent=2, ensure_ascii=True, default=str) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(payload)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def update_manifest_run_status(
    workspace: RunWorkspace,
    stages: tuple[StageSpec, ...],
    *,
    run_status: str,
    last_event: str,
    current_stage_slug: str | None = None,
    last_error: str | None = None,
    completed_at: str | None = None,
) -> RunManifest:
    manifest = ensure_run_manifest(workspace, stages)
    updated = RunManifest(
        run_id=manifest.run_id,
        created_at=manifest.created_at,
        updated_at=utc_now(),
        run_status=run_status,
        last_event=last_event,
        current_stage_slug=current_stage_slug,
        last_error=last_error,
        completed_at=completed_at,
        stages=manifest.stages,
    )
    save_run_manifest(workspace.run_manifest, updated)
    return updated


def update_stage_entry(
    workspace: RunWorkspace,
    stages: tuple[StageSpec, ...],
    stage: StageSpec,
    **changes: object,
) -> RunManifest:
    manifest = ensure_run_manifest(workspace, stages)
    updated_stages: list[StageManifestEntry] = []
    for entry in manifest.stages:
        if entry.slug != stage.slug:
            updated_stages.append(entry)
            continue
        payload = entry.to_dict()
        payload.update(changes)
        payload["updated_at"] = utc_now()
        updated_stages.append(StageManifestEntry.from_dict(payload))
    updated = RunManifest(
        run_id=manifest.run_id,
        created_at=manifest.created_at,
        updated_at=utc_now(),
        run_status=manifest.run_status,
        last_event=manifest.last_event,
        current_stage_slug=manifest.current_stage_slug,
        last_error=manifest.last_error,
        completed_at=manifest.completed_at,
        stages=tuple(updated_stages),
    )
    save_run_manifest(workspace.run_manifest, updated)
    return updated


def mark_stage_running_manifest(
    workspace: RunWorkspace,
    stages: tuple[StageSpec, ...],
    stage: StageSpec,
    attempt_no: int,
) -> RunManifest:
    update_manifest_run_status(
        workspace,
        stages,
        run_status="running",
        last_event="stage.started",
        current_stage_slug=stage.slug,
    )
    return update_stage_entry(
        workspace,
        stages,
        stage,
        status="running",
        approved=False,
        dirty=False,
        stale=False,
        attempt_count=attempt_no,
        last_error=None,
    )


def mark_stage_review_manifest(
    workspace: RunWorkspace,
    stages: tuple[StageSpec, ...],
    stage: StageSpec,
    attempt_no: int,
    artifact_paths: tuple[str, ...] | list[str],
) -> RunManifest:
    update_manifest_run_status(
        workspace,
        stages,
        run_status="human_review",
        last_event="stage.awaiting_review",
        current_stage_slug=stage.slug,
    )
    return update_stage_entry(
        workspace,
        stages,
        stage,
        status="human_review",
        approved=False,
        dirty=False,
        stale=False,
        attempt_count=attempt_no,
        artifact_paths=tuple(artifact_paths),
    )


def mark_stage_approved_manifest(
    workspace: RunWorkspace,
    stages: tuple[StageSpec, ...],
    stage: StageSpec,
    attempt_no: int,
    artifact_paths: tuple[str, ...] | list[str],
) -> RunManifest:
    update_manifest_run_status(
        workspace,
        stages,
        run_status="pending",
        last_event="stage.approved",
        current_stage_slug=None,
        last_error=None,
    )
    return update_stage_entry(
        workspace,
        stages,
        stage,
        status="approved",
        approved=True,
        dirty=False,
        stale=False,
        attempt_count=attempt_no,
        artifact_paths=tuple(artifact_paths),
        last_error=None,
        approved_at=utc_now(),
    )


def mark_stage_failed_manifest(
    workspace: RunWorkspace,
    stages: tuple[StageSpec, ...],
    stage: StageSpec,
    error: str,
) -> RunManifest:
    update_manifest_run_status(
        workspace,
        stages,
        run_status="failed",
        last_event="stage.failed",
        current_stage_slug=stage.slug,
        last_error=error,
    )
    return update_stage_entry(
        workspace,
        stages,
        stage,
        status="failed",
        approved=False,
        dirty=True,
        stale=False,
        last_error=error,
    )


def sync_stage_session_id(
    workspace: RunWorkspace,
    stages: tuple[StageSpec, ...],
    stage: StageSpec,
    session_id: str | None,
) -> RunManifest:
    return update_stage_entry(workspace, stages, stage, session_id=session_id)


def rollback_to_stage(
    workspace: RunWorkspace,
    stages: tuple[StageSpec, ...],
    rollback_stage: StageSpec,
    reason: str | None = None,
) -> RunManifest:
    manifest = ensure_run_manifest(workspace, stages)
    invalidated_reason = reason or f"Rolled back to {rollback_stage.title}"
    updated_stages: list[StageManifestEntry] = []
    for entry in manifest.stages:
        payload = entry.to_dict()
        if entry.number < rollback_stage.number:
            updated_stages.append(entry)
            continue
        if entry.number == rollback_stage.number:
            payload.update(
                {
                    "status": "pending",
                    "approved": False,
                    "dirty": True,
                    "stale": False,
                    "approved_at": None,
                    "invalidated_reason": invalidated_reason,
                    "invalidated_by_stage": rollback_stage.slug,
                }
            )
        else:
            payload.update(
                {
                    "status": "stale",
                    "approved": False,
                    "dirty": True,
                    "stale": True,
                    "approved_at": None,
                    "invalidated_reason": invalidated_reason,
                    "invalidated_by_stage": rollback_stage.slug,
                }
            )
        payload["updated_at"] = utc_now()
        updated_stages.append(StageManifestEntry.from_dict(payload))

    updated = RunManifest(
        run_id=manifest.run_id,
        created_at=manifest.created_at,
        updated_at=utc_now(),
        run_status="pending",
        last_event="run.rolled_back",
        current_stage_slug=rollback_stage.slug,
        last_error=None,
        completed_at=None,
        stages=tuple(updated_stages),
    )
    save_run_manifest(workspace.run_manifest, updated)
    return updated


def select_pending_stages(
    workspace: RunWorkspace,
    stages: tuple[StageSpec, ...],
    start_stage: StageSpec | None = None,
) -> tuple[StageSpec, ...]:
    if start_stage is not None:
        return tuple(stage for stage in stages if stage.number >= start_stage.number)
    manifest = ensure_run_manifest(workspace, stages)
    entries = {entry.slug: entry for entry in manifest.stages}
    return tuple(
        stage
        for stage in stages
        if not (entries.get(stage.slug) and entries[stage.slug].approved and entries[stage.slug].status == "approved")
    )


def format_manifest_status(manifest: RunManifest) -> str:
    lines = [
        f"Run: {manifest.run_id}",
        f"Updated At: {manifest.updated_at}",
        f"Run Status: {manifest.run_status}",
        f"Last Event: {manifest.last_event}",
        f"Current Stage: {manifest.current_stage_slug or 'None'}",
        "Stages:",
    ]
    for entry in manifest.stages:
        flags: list[str] = []
        if entry.approved:
            flags.append("approved")
        if entry.dirty:
            flags.append("dirty")
        if entry.stale:
            flags.append("stale")
        suffix = f" [{' '.join(flags)}]" if flags else ""
        lines.append(
            f"- {entry.slug}: status={entry.status}, attempts={entry.attempt_count}, "
            f"session_id={entry.session_id or 'none'}{suffix}"
        )
    return "\n".join(lines)
