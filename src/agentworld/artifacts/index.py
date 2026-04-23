from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from ..utils import utc_now
from .models import ArtifactIndex, ArtifactRecord, ArtifactRequirement, ArtifactValidationResult, resolve_requirement

DATA_SUFFIXES = {".csv", ".json", ".jsonl", ".parquet", ".tsv", ".yaml", ".yml"}
RESULT_SUFFIXES = {".json", ".jsonl", ".csv", ".tsv", ".npz", ".npy", ".md"}
FIGURE_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".svg"}
WRITING_SUFFIXES = {".md", ".tex", ".bib", ".pdf"}


def scan_artifacts(workspace_root: Path) -> ArtifactIndex:
    root = Path(workspace_root)
    records: list[ArtifactRecord] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.endswith(".schema.json"):
            continue
        if path.name == "experiment_manifest.json" and path.parent.name == "results":
            continue
        relative_path = str(path.relative_to(root))
        suffix = path.suffix.lower()
        category = categorize_artifact(relative_path, suffix)
        if category is None:
            continue
        stat = path.stat()
        records.append(
            ArtifactRecord(
                category=category,
                relative_path=relative_path,
                suffix=suffix,
                size_bytes=stat.st_size,
                filename=path.name,
                updated_at=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                schema=infer_schema(path, category, root),
            )
        )
    return ArtifactIndex(generated_at=utc_now(), artifacts=tuple(records))


def write_artifact_index(index_path: Path, workspace_root: Path) -> ArtifactIndex:
    index = scan_artifacts(workspace_root)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index.to_dict(), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return index


def load_artifact_index(path: Path) -> ArtifactIndex | None:
    if not path.exists():
        return None
    return ArtifactIndex.from_dict(json.loads(path.read_text(encoding="utf-8")))


def format_artifact_index_for_prompt(index: ArtifactIndex, max_entries_per_category: int = 5) -> str:
    if not index.artifacts:
        return "No structured data, result, figure, code, note, or writing artifacts have been indexed yet."

    lines = [
        f"Artifact index generated at: {index.generated_at}",
        f"Indexed artifacts: {index.artifact_count}",
    ]
    categories = sorted({artifact.category for artifact in index.artifacts})
    for category in categories:
        entries = [artifact for artifact in index.artifacts if artifact.category == category]
        if not entries:
            continue
        lines.append(f"\n### {category.title()}")
        for artifact in entries[:max_entries_per_category]:
            schema_bits = schema_summary(artifact.schema)
            suffix_label = artifact.suffix.lstrip(".") or "file"
            summary = f"- `{artifact.relative_path}` ({suffix_label}, {artifact.size_bytes} bytes)"
            if schema_bits:
                summary += f" | {schema_bits}"
            lines.append(summary)
        remaining = len(entries) - max_entries_per_category
        if remaining > 0:
            lines.append(f"- ... {remaining} more {category} artifacts indexed.")
    return "\n".join(lines)


def indexed_artifacts_for_category(index: ArtifactIndex, category: str) -> list[dict[str, object]]:
    return [artifact.to_dict() for artifact in index.artifacts if artifact.category == category]


def validate_artifact_requirements(
    *,
    run_root: Path,
    requirements: list[ArtifactRequirement] | tuple[ArtifactRequirement, ...],
) -> ArtifactValidationResult:
    missing: list[str] = []
    present: list[str] = []
    for requirement in requirements:
        path = resolve_requirement(run_root, requirement)
        if path.exists():
            present.append(requirement.relative_path)
        elif requirement.required:
            missing.append(requirement.relative_path)
    return ArtifactValidationResult(ok=not missing, missing=tuple(missing), present=tuple(present))


def categorize_artifact(relative_path: str, suffix: str) -> str | None:
    first = relative_path.split("/", 1)[0]
    if first == "data" and suffix in DATA_SUFFIXES:
        return "data"
    if first == "results" and suffix in RESULT_SUFFIXES:
        return "results"
    if first == "figures" and suffix in FIGURE_SUFFIXES:
        return "figures"
    if first == "writing" and suffix in WRITING_SUFFIXES:
        return "writing"
    if first == "artifacts":
        return "artifact"
    if first == "literature" and suffix in {".md", ".bib", ".json", ".csv"}:
        return "literature"
    if first == "notes" and suffix in {".md", ".json"}:
        return "notes"
    if first == "code" and suffix in {".py", ".sh", ".R", ".jl", ".ipynb"}:
        return "code"
    return None


def infer_schema(path: Path, category: str, workspace_root: Path) -> dict[str, object]:
    sidecar_path = path.parent / f"{path.name}.schema.json"
    if sidecar_path.exists():
        try:
            declared = json.loads(sidecar_path.read_text(encoding="utf-8"))
            return {
                "source": "declared",
                "sidecar_path": str(sidecar_path.relative_to(workspace_root)),
                "definition": declared,
            }
        except json.JSONDecodeError:
            return {
                "source": "declared",
                "sidecar_path": str(sidecar_path.relative_to(workspace_root)),
                "error": "invalid_json",
            }

    suffix = path.suffix.lower()
    if suffix == ".json":
        return _infer_json_schema(path)
    if suffix == ".jsonl":
        return _infer_jsonl_schema(path)
    if suffix in {".csv", ".tsv"}:
        return _infer_tabular_schema(path, delimiter="\t" if suffix == ".tsv" else ",")
    if suffix in {".yaml", ".yml"}:
        return {"source": "inferred", "kind": "yaml_document"}
    if suffix == ".parquet":
        return {"source": "inferred", "kind": "parquet_table"}
    if suffix == ".npz":
        return {"source": "inferred", "kind": "numpy_archive"}
    if suffix == ".npy":
        return {"source": "inferred", "kind": "numpy_array"}
    if category == "figures":
        return {"source": "inferred", "kind": "figure", "format": suffix.lstrip(".")}
    return {"source": "inferred", "kind": "file"}


def schema_summary(schema: dict[str, object]) -> str:
    if not schema:
        return ""
    parts: list[str] = []
    kind = str(schema.get("kind") or schema.get("source") or "").strip()
    if kind:
        parts.append(kind)
    for key in ("columns", "keys", "item_keys"):
        value = schema.get(key)
        if isinstance(value, list) and value:
            parts.append(f"{key}=" + ", ".join(str(item) for item in value[:6]))
    if "row_count" in schema:
        parts.append(f"rows={schema['row_count']}")
    if "item_count" in schema:
        parts.append(f"items={schema['item_count']}")
    if "sidecar_path" in schema:
        parts.append(f"schema={schema['sidecar_path']}")
    if "error" in schema:
        parts.append(f"error={schema['error']}")
    return ", ".join(parts)


def _infer_json_schema(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"source": "inferred", "kind": "json", "error": "invalid_json"}
    if isinstance(payload, dict):
        return {
            "source": "inferred",
            "kind": "object",
            "keys": sorted(str(key) for key in payload.keys())[:20],
        }
    if isinstance(payload, list):
        item_keys: set[str] = set()
        for item in payload[:20]:
            if isinstance(item, dict):
                item_keys.update(str(key) for key in item.keys())
        schema: dict[str, object] = {
            "source": "inferred",
            "kind": "array",
            "item_count": len(payload),
        }
        if item_keys:
            schema["item_keys"] = sorted(item_keys)
        return schema
    return {"source": "inferred", "kind": type(payload).__name__}


def _infer_jsonl_schema(path: Path) -> dict[str, object]:
    row_count = 0
    keys: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            row_count += 1
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                return {"source": "inferred", "kind": "jsonl", "error": "invalid_jsonl"}
            if isinstance(payload, dict):
                keys.update(str(key) for key in payload.keys())
    schema: dict[str, object] = {
        "source": "inferred",
        "kind": "jsonl",
        "row_count": row_count,
    }
    if keys:
        schema["keys"] = sorted(keys)
    return schema


def _infer_tabular_schema(path: Path, delimiter: str) -> dict[str, object]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter=delimiter))
    if not rows:
        return {"source": "inferred", "kind": "table", "columns": [], "row_count": 0}
    return {
        "source": "inferred",
        "kind": "table",
        "columns": [column.strip() for column in rows[0]],
        "row_count": max(len(rows) - 1, 0),
    }
