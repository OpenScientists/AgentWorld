from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..artifacts import indexed_artifacts_for_category, write_artifact_index
from ..utils import utc_now
from ..workspace import RunWorkspace


@dataclass(frozen=True, slots=True)
class ExperimentManifest:
    generated_at: str
    ready_for_analysis: bool
    result_artifacts: tuple[dict[str, object], ...]
    code_artifacts: tuple[str, ...]
    note_artifacts: tuple[str, ...]
    summary: dict[str, int]
    summary_extras: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "ready_for_analysis": self.ready_for_analysis,
            "result_artifacts": list(self.result_artifacts),
            "code_artifacts": list(self.code_artifacts),
            "note_artifacts": list(self.note_artifacts),
            "summary": {**self.summary, **self.summary_extras},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ExperimentManifest":
        summary_raw = dict(payload.get("summary", {}))
        summary: dict[str, int] = {}
        summary_extras: dict[str, object] = {}
        for key, value in summary_raw.items():
            coerced = _coerce_summary_int(value)
            if coerced is None:
                summary_extras[str(key)] = value
            else:
                summary[str(key)] = coerced
        return cls(
            generated_at=str(payload.get("generated_at") or "").strip(),
            ready_for_analysis=bool(payload.get("ready_for_analysis", False)),
            result_artifacts=tuple(
                dict(item)
                for item in payload.get("result_artifacts", [])
                if isinstance(item, dict)
            ),
            code_artifacts=tuple(str(item) for item in payload.get("code_artifacts", []) if str(item).strip()),
            note_artifacts=tuple(str(item) for item in payload.get("note_artifacts", []) if str(item).strip()),
            summary=summary,
            summary_extras=summary_extras,
        )


def write_experiment_manifest(workspace: RunWorkspace) -> ExperimentManifest:
    existing = load_experiment_manifest(workspace.experiment_manifest)
    artifact_index = write_artifact_index(workspace.artifact_index, workspace.workspace_root)
    result_artifacts = tuple(
        artifact
        for artifact in indexed_artifacts_for_category(artifact_index, "results")
        if artifact.get("rel_path") != "results/experiment_manifest.json"
        and artifact.get("relative_path") != "results/experiment_manifest.json"
    )
    code_artifacts = tuple(_list_relative_files(workspace.code_dir, workspace.workspace_root))
    note_artifacts = tuple(_list_relative_files(workspace.notes_dir, workspace.workspace_root))
    manifest = ExperimentManifest(
        generated_at=utc_now(),
        ready_for_analysis=bool(result_artifacts),
        result_artifacts=result_artifacts,
        code_artifacts=code_artifacts,
        note_artifacts=note_artifacts,
        summary={
            "result_artifact_count": len(result_artifacts),
            "code_artifact_count": len(code_artifacts),
            "note_artifact_count": len(note_artifacts),
        },
        summary_extras=dict(existing.summary_extras) if existing is not None else {},
    )
    workspace.experiment_manifest.parent.mkdir(parents=True, exist_ok=True)
    workspace.experiment_manifest.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_experiment_manifest(path: Path) -> ExperimentManifest | None:
    if not path.exists():
        return None
    return ExperimentManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))


def validate_experiment_manifest(path: Path) -> list[str]:
    manifest = load_experiment_manifest(path)
    if manifest is None:
        return ["Missing experiment_manifest.json."]
    problems: list[str] = []
    if not manifest.generated_at:
        problems.append("experiment_manifest.json is missing generated_at.")
    for key in ("result_artifact_count", "code_artifact_count", "note_artifact_count"):
        if key not in manifest.summary:
            problems.append(f"experiment_manifest.json is missing summary.{key}.")
    if not isinstance(manifest.ready_for_analysis, bool):
        problems.append("experiment_manifest.json must contain a boolean ready_for_analysis field.")
    for artifact in manifest.result_artifacts:
        rel_path = str(artifact.get("relative_path") or artifact.get("rel_path") or "").strip()
        if not rel_path:
            problems.append("experiment_manifest.json contains a result artifact without rel_path.")
            continue
        if not isinstance(artifact.get("schema"), dict):
            problems.append(f"experiment_manifest.json result artifact `{rel_path}` is missing schema metadata.")
    return problems


def format_experiment_manifest_for_prompt(manifest: ExperimentManifest, max_results: int = 5) -> str:
    lines = [
        f"Experiment manifest generated at: {manifest.generated_at}",
        f"Ready for analysis: {'yes' if manifest.ready_for_analysis else 'no'}",
        (
            "Summary: "
            f"{manifest.summary.get('result_artifact_count', 0)} result artifacts, "
            f"{manifest.summary.get('code_artifact_count', 0)} code artifacts, "
            f"{manifest.summary.get('note_artifact_count', 0)} note artifacts"
        ),
    ]
    if manifest.result_artifacts:
        lines.append("\n### Result Artifacts")
        for artifact in manifest.result_artifacts[:max_results]:
            rel_path = str(artifact.get("relative_path") or artifact.get("rel_path") or "").strip()
            summary = _format_schema(artifact.get("schema"))
            line = f"- `{rel_path}`"
            if summary:
                line += f" | {summary}"
            lines.append(line)
    if manifest.code_artifacts:
        lines.append("\n### Supporting Code")
        lines.extend(f"- `{path}`" for path in manifest.code_artifacts[:max_results])
    if manifest.note_artifacts:
        lines.append("\n### Experiment Notes")
        lines.extend(f"- `{path}`" for path in manifest.note_artifacts[:max_results])
    if manifest.summary_extras:
        lines.append("\n### Additional Summary Fields")
        for key, value in manifest.summary_extras.items():
            rendered = json.dumps(value, ensure_ascii=True, sort_keys=True) if isinstance(value, (dict, list)) else value
            lines.append(f"- {key}: {rendered}")
    return "\n".join(lines)


def _list_relative_files(directory: Path, workspace_root: Path) -> list[str]:
    if not directory.exists():
        return []
    return sorted(str(path.relative_to(workspace_root)) for path in directory.rglob("*") if path.is_file())


def _format_schema(schema: object) -> str:
    if not isinstance(schema, dict) or not schema:
        return ""
    pieces: list[str] = []
    kind = str(schema.get("kind") or schema.get("source") or "").strip()
    if kind:
        pieces.append(kind)
    for key in ("columns", "keys", "item_keys"):
        value = schema.get(key)
        if isinstance(value, list) and value:
            pieces.append(f"{key}=" + ", ".join(str(item) for item in value[:6]))
    if "row_count" in schema:
        pieces.append(f"rows={schema['row_count']}")
    if "item_count" in schema:
        pieces.append(f"items={schema['item_count']}")
    return ", ".join(pieces)


def _coerce_summary_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return None
