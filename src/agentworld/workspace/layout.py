from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RunWorkspace:
    """Filesystem contract for one durable workflow run."""

    run_root: Path
    goal: Path
    user_input: Path
    memory: Path
    run_config: Path
    run_manifest: Path
    artifact_index: Path
    logs: Path
    logs_raw_dir: Path
    events: Path
    prompt_cache_dir: Path
    operator_state_dir: Path
    stages_dir: Path
    handoffs_dir: Path
    workspace_root: Path
    literature_dir: Path
    code_dir: Path
    data_dir: Path
    results_dir: Path
    experiment_manifest: Path
    hypothesis_manifest: Path
    figures_dir: Path
    writing_dir: Path
    notes_dir: Path
    reviews_dir: Path
    artifacts_dir: Path
    bootstrap_dir: Path
    profile_dir: Path
    intake_context: Path

    def stage_draft_path(self, slug: str) -> Path:
        return self.stages_dir / f"{slug}.tmp.md"

    def stage_final_path(self, slug: str) -> Path:
        return self.stages_dir / f"{slug}.md"

    def stage_session_file(self, slug: str) -> Path:
        return self.operator_state_dir / f"{slug}.session_id.txt"

    def stage_session_state_file(self, slug: str) -> Path:
        return self.operator_state_dir / f"{slug}.session.json"

    def stage_attempt_state_file(self, slug: str, attempt: int) -> Path:
        return self.operator_state_path(slug, attempt)

    def stage_execution_marker_file(self, slug: str) -> Path:
        return self.operator_state_dir / f"{slug}.started_at.txt"

    def prompt_path(self, slug: str, attempt: int) -> Path:
        return self.prompt_cache_dir / f"{slug}.attempt_{attempt:02d}.prompt.md"

    def operator_state_path(self, slug: str, attempt: int) -> Path:
        return self.operator_state_dir / f"{slug}.attempt_{attempt:02d}.json"


DEFAULT_WORKSPACE_DIRS = (
    "literature",
    "code",
    "data",
    "results",
    "figures",
    "writing",
    "notes",
    "reviews",
    "artifacts",
    "bootstrap",
    "profile",
)


def make_run_id(now: datetime | None = None) -> str:
    timestamp = now or datetime.now(timezone.utc)
    return timestamp.strftime("%Y%m%d_%H%M%S")


def unique_run_root(runs_dir: Path, *, run_id: str | None = None) -> Path:
    runs_dir = Path(runs_dir)
    base = run_id or make_run_id()
    candidate = runs_dir / base
    counter = 1
    while candidate.exists():
        candidate = runs_dir / f"{base}_{counter:02d}"
        counter += 1
    return candidate


def build_run_workspace(run_root: Path) -> RunWorkspace:
    run_root = Path(run_root)
    workspace_root = run_root / "workspace"
    return RunWorkspace(
        run_root=run_root,
        goal=run_root / "goal.md",
        user_input=run_root / "user_input.txt",
        memory=run_root / "memory.md",
        run_config=run_root / "run_config.json",
        run_manifest=run_root / "run_manifest.json",
        artifact_index=run_root / "artifact_index.json",
        logs=run_root / "logs.txt",
        logs_raw_dir=run_root / "logs_raw",
        events=run_root / "events.jsonl",
        prompt_cache_dir=run_root / "prompt_cache",
        operator_state_dir=run_root / "operator_state",
        stages_dir=run_root / "stages",
        handoffs_dir=run_root / "handoffs",
        workspace_root=workspace_root,
        literature_dir=workspace_root / "literature",
        code_dir=workspace_root / "code",
        data_dir=workspace_root / "data",
        results_dir=workspace_root / "results",
        experiment_manifest=workspace_root / "results" / "experiment_manifest.json",
        hypothesis_manifest=workspace_root / "notes" / "hypothesis_manifest.json",
        figures_dir=workspace_root / "figures",
        writing_dir=workspace_root / "writing",
        notes_dir=workspace_root / "notes",
        reviews_dir=workspace_root / "reviews",
        artifacts_dir=workspace_root / "artifacts",
        bootstrap_dir=workspace_root / "bootstrap",
        profile_dir=workspace_root / "profile",
        intake_context=workspace_root / "notes" / "intake_context.json",
    )


def workspace_directories(paths: RunWorkspace) -> list[Path]:
    return [
        paths.prompt_cache_dir,
        paths.operator_state_dir,
        paths.stages_dir,
        paths.handoffs_dir,
        paths.logs_raw_dir,
        paths.workspace_root,
        paths.literature_dir,
        paths.code_dir,
        paths.data_dir,
        paths.results_dir,
        paths.figures_dir,
        paths.writing_dir,
        paths.notes_dir,
        paths.reviews_dir,
        paths.artifacts_dir,
        paths.bootstrap_dir,
        paths.profile_dir,
    ]


def ensure_run_workspace(paths: RunWorkspace) -> None:
    paths.run_root.mkdir(parents=True, exist_ok=True)
    for directory in workspace_directories(paths):
        directory.mkdir(parents=True, exist_ok=True)
    for file_path in (paths.goal, paths.user_input, paths.memory, paths.logs, paths.events):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch(exist_ok=True)


def relative_to_run(paths: RunWorkspace, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(paths.run_root.resolve()))
    except ValueError:
        return str(path)
