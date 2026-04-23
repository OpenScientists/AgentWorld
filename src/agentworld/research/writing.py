from __future__ import annotations

from pathlib import Path

from ..artifacts import scan_artifacts
from ..stage.markdown import extract_markdown_section
from ..workspace import RunWorkspace, read_text


def build_writing_manifest(workspace: RunWorkspace) -> dict[str, object]:
    return {
        "writing_files": _scan_dir(workspace.writing_dir),
        "figure_files": _scan_dir(workspace.figures_dir),
        "result_files": _scan_dir(workspace.results_dir),
        "stage_summaries": _collect_stage_summaries(workspace),
        "artifact_index": scan_artifacts(workspace.workspace_root).to_dict(),
    }


def format_writing_manifest_for_prompt(manifest: dict[str, object]) -> str:
    lines = ["Writing bundle context:"]
    for label, key in (
        ("Writing Files", "writing_files"),
        ("Figures", "figure_files"),
        ("Results", "result_files"),
    ):
        values = manifest.get(key)
        if isinstance(values, list) and values:
            lines.append(f"\n### {label}")
            lines.extend(f"- `{item}`" for item in values[:20])
    stage_summaries = manifest.get("stage_summaries")
    if isinstance(stage_summaries, dict) and stage_summaries:
        lines.append("\n### Approved Stage Summary Excerpts")
        for slug, summary in stage_summaries.items():
            lines.append(f"- {slug}: {summary}")
    return "\n".join(lines)


def _scan_dir(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    workspace_root = directory.parent
    return sorted(str(path.relative_to(workspace_root)) for path in directory.rglob("*") if path.is_file())


def _collect_stage_summaries(workspace: RunWorkspace) -> dict[str, str]:
    summaries: dict[str, str] = {}
    for path in sorted(workspace.stages_dir.glob("*.md")):
        text = read_text(path)
        key_results = extract_markdown_section(text, "Key Results")
        if key_results:
            summaries[path.stem] = key_results[:600].strip()
    return summaries
