from __future__ import annotations

from ..workspace import RunWorkspace, read_text, write_text
from .markdown import extract_markdown_section, strip_markdown_section
from .models import StageSpec


def render_approved_stage_entry(stage: StageSpec, stage_markdown: str) -> str:
    objective = extract_markdown_section(stage_markdown, "Objective") or "Not provided."
    what_i_did = extract_markdown_section(stage_markdown, "What I Did") or "Not provided."
    key_results = extract_markdown_section(stage_markdown, "Key Results") or "Not provided."
    files_produced = extract_markdown_section(stage_markdown, "Files Produced") or "Not provided."
    return (
        f"### {stage.title}\n\n"
        "#### Objective\n"
        f"{objective}\n\n"
        "#### What I Did\n"
        f"{what_i_did}\n\n"
        "#### Key Results\n"
        f"{key_results}\n\n"
        "#### Files Produced\n"
        f"{files_produced}"
    )


def build_memory_text(user_goal: str, approved_entries: list[str], intake_summary: str | None = None) -> str:
    approved_block = "\n\n".join(entry.strip() for entry in approved_entries if entry.strip()) or "_None yet._"
    parts = [
        "# Approved Run Memory\n",
        "## Original User Goal\n"
        f"{user_goal.strip()}\n",
    ]
    if intake_summary:
        parts.append(
            "## Intake Resources and Clarifications\n"
            f"{intake_summary.strip()}\n"
        )
    parts.append(
        "## Approved Stage Summaries\n\n"
        f"{approved_block}\n"
    )
    return "\n".join(parts)


def approved_stage_summaries(memory_text: str) -> str:
    marker = "## Approved Stage Summaries"
    if marker not in memory_text:
        return "None yet."
    content = memory_text.split(marker, 1)[1].strip()
    if not content or content == "_None yet._":
        return "None yet."
    return content


def append_approved_stage_summary(workspace: RunWorkspace, stage: StageSpec, stage_markdown: str) -> None:
    current = read_text(workspace.memory)
    user_goal = extract_markdown_section(current, "Original User Goal") or read_text(workspace.goal)
    intake_summary = extract_markdown_section(current, "Intake Resources and Clarifications")
    retained_entries = [
        entry
        for number, entry in approved_stage_entries(current)
        if number < stage.number
    ]
    retained_entries.append(render_approved_stage_entry(stage, stage_markdown))
    write_text(workspace.memory, build_memory_text(user_goal, retained_entries, intake_summary=intake_summary))


def approved_stage_entries(memory_text: str) -> list[tuple[int, str]]:
    summaries = approved_stage_summaries(memory_text)
    if summaries == "None yet.":
        return []
    import re

    pattern = re.compile(r"^### Stage (\d+): .*$", flags=re.MULTILINE)
    matches = list(pattern.finditer(summaries))
    entries: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(summaries)
        entries.append((int(match.group(1)), summaries[start:end].strip()))
    return entries


def filtered_approved_memory(memory_text: str, max_stage_number: int) -> str:
    user_goal = extract_markdown_section(memory_text, "Original User Goal") or ""
    intake_summary = extract_markdown_section(memory_text, "Intake Resources and Clarifications")
    kept_entries = [
        entry
        for number, entry in approved_stage_entries(memory_text)
        if number <= max_stage_number
    ]
    return build_memory_text(user_goal, kept_entries, intake_summary=intake_summary)


def rebuild_memory_from_manifest(
    workspace: RunWorkspace,
    stages: tuple[StageSpec, ...],
    approved_slugs: set[str],
) -> None:
    entries: list[str] = []
    for stage in stages:
        if stage.slug not in approved_slugs:
            continue
        final_path = workspace.stage_final_path(stage.slug)
        if final_path.exists():
            entries.append(render_approved_stage_entry(stage, read_text(final_path)))
    write_text(workspace.memory, build_memory_text(read_text(workspace.goal), entries))


def write_stage_handoff(workspace: RunWorkspace, stage: StageSpec, stage_markdown: str):
    handoff_path = workspace.handoffs_dir / f"{stage.slug}.md"
    objective = extract_markdown_section(stage_markdown, "Objective") or "Not provided."
    key_results = extract_markdown_section(stage_markdown, "Key Results") or "Not provided."
    files_produced = extract_markdown_section(stage_markdown, "Files Produced") or "Not provided."
    decision_ledger = extract_markdown_section(stage_markdown, "Decision Ledger")
    parts = [
        f"# Handoff: {stage.title}\n\n"
        "## Objective\n"
        f"{objective}\n\n"
        "## Key Results\n"
        f"{key_results}\n\n"
        "## Files Produced\n"
        f"{files_produced}\n",
    ]
    if decision_ledger:
        parts.append(
            "\n## Decision Ledger\n"
            f"{decision_ledger}\n"
        )
    write_text(handoff_path, "".join(parts))
    return handoff_path


def build_handoff_context(workspace: RunWorkspace, upto_stage: StageSpec | None = None, max_stages: int = 4) -> str:
    handoffs = sorted(path for path in workspace.handoffs_dir.glob("*.md") if path.is_file())
    if upto_stage is not None:
        handoffs = [path for path in handoffs if path.stem < upto_stage.slug]
    handoffs = handoffs[-max_stages:]
    parts = [
        strip_markdown_section(read_text(path).strip(), "Decision Ledger")
        for path in handoffs
        if path.exists()
    ]
    return "\n\n".join(parts).strip() or "No stage handoff summaries available yet."


def build_decision_ledger_context(workspace: RunWorkspace, upto_stage: StageSpec | None = None) -> str | None:
    handoffs = sorted(path for path in workspace.handoffs_dir.glob("*.md") if path.is_file())
    if upto_stage is not None:
        handoffs = [path for path in handoffs if path.stem < upto_stage.slug]
    entries: list[str] = []
    for handoff_path in handoffs:
        content = read_text(handoff_path)
        ledger = extract_markdown_section(content, "Decision Ledger")
        if not ledger:
            continue
        stage_name = handoff_path.stem.replace("_", " ").title()
        for line in content.splitlines():
            if line.startswith("# Handoff:"):
                stage_name = line.removeprefix("# Handoff:").strip()
                break
        entries.append(f"### {stage_name}\n{ledger}")
    return "\n\n".join(entries) if entries else None
