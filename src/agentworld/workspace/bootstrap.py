from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..utils import utc_now
from .layout import RunWorkspace, build_run_workspace, ensure_run_workspace, unique_run_root


def create_run_workspace(
    *,
    runs_dir: Path,
    goal: str,
    run_id: str | None = None,
    config: dict[str, Any] | None = None,
) -> RunWorkspace:
    run_root = unique_run_root(runs_dir, run_id=run_id)
    paths = build_run_workspace(run_root)
    ensure_run_workspace(paths)
    write_text(paths.goal, goal)
    write_text(paths.user_input, goal)
    write_text(paths.memory, _initial_memory(goal))
    write_json(
        paths.run_config,
        {
            "run_id": paths.run_root.name,
            "created_at": utc_now(),
            **dict(config or {}),
        },
    )
    return paths


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, indent=2, ensure_ascii=True, default=str))


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    append_text(path, json.dumps(payload, ensure_ascii=True, default=str) + "\n")


def _initial_memory(goal: str) -> str:
    return "\n".join(
        [
            "# Run Memory",
            "",
            "## Goal",
            goal.strip(),
            "",
            "## Approved Stage Summaries",
            "_None yet._",
        ]
    )
