from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..workspace import RunWorkspace
    from .models import StageSpec


REQUIRED_STAGE_HEADINGS = (
    "Objective",
    "Previously Approved Stage Summaries",
    "What I Did",
    "Key Results",
    "Files Produced",
    "Decision Ledger",
    "Suggestions for Refinement",
    "Your Options",
)

FIXED_STAGE_OPTIONS = (
    "1. Use suggestion 1",
    "2. Use suggestion 2",
    "3. Use suggestion 3",
    "4. Refine with your own feedback",
    "5. Approve and continue",
    "6. Abort",
)

TYPED_HYPOTHESIS_HEADINGS = (
    "Theoretical Propositions",
    "Empirical Hypotheses",
    "Paper Claims (Provisional)",
)

PLACEHOLDER_PATTERNS = (
    r"\[todo\]",
    r"\[tbd\]",
    r"\[pending\]",
    r"\[placeholder\]",
    r"\[in progress\]",
    r"\[insert\b",
    r"\bTODO\b",
    r"\bTBD\b",
)


@dataclass(frozen=True, slots=True)
class StageValidationResult:
    ok: bool
    errors: tuple[str, ...] = ()


def extract_markdown_section(markdown: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*$\n?(.*?)(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown)
    if match is None:
        return None
    return match.group(1).strip()


def strip_markdown_section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*$\n?.*?(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    return pattern.sub("", markdown).strip()


def parse_numbered_list(section_text: str) -> dict[int, str]:
    items: dict[int, str] = {}
    for raw_line in section_text.splitlines():
        match = re.match(r"^\s*(\d+)\.\s+(.*?)\s*$", raw_line)
        if match:
            items[int(match.group(1))] = match.group(2).strip()
    return items


def parse_numbered_list_sequence(section_text: str) -> list[int]:
    sequence: list[int] = []
    for raw_line in section_text.splitlines():
        match = re.match(r"^\s*(\d+)\.\s+", raw_line)
        if match:
            sequence.append(int(match.group(1)))
    return sequence


def parse_refinement_suggestions(markdown: str) -> list[str]:
    section = extract_markdown_section(markdown, "Suggestions for Refinement")
    if section is None:
        raise ValueError("Missing required section: Suggestions for Refinement")
    items = parse_numbered_list(section)
    return [items[index] for index in sorted(items)]


def extract_revision_delta(markdown: str) -> str | None:
    pattern = re.compile(
        r"^## Revision Delta\s*$\n?(.*?)(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown)
    if match is None:
        return None
    return match.group(1).strip()


def strip_revision_delta(markdown: str) -> str:
    pattern = re.compile(
        r"^## Revision Delta\s*$\n?.*?(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    return pattern.sub("", markdown).strip() + "\n"


def contains_placeholder_text(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in PLACEHOLDER_PATTERNS)


def extract_path_references(text: str) -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []
    for candidate in re.findall(r"`([^`]+)`", text):
        normalized = candidate.strip()
        if not normalized or "/" not in normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        paths.append(normalized)
    return paths


def extract_typed_hypothesis_sections(stage_markdown: str) -> dict[str, str]:
    key_results = extract_markdown_section(stage_markdown, "Key Results")
    if not key_results:
        return {}
    pattern = re.compile(
        r"^### (Theoretical Propositions|Empirical Hypotheses|Paper Claims \(Provisional\))\s*$\n?(.*?)(?=^### |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    return {match.group(1).strip(): match.group(2).strip() for match in pattern.finditer(key_results)}


def validate_stage_markdown(
    markdown: str,
    stage: "StageSpec",
    workspace: "RunWorkspace | None" = None,
) -> StageValidationResult:
    problems: list[str] = []
    lines = markdown.splitlines()
    first_nonempty_line = next((line.strip() for line in lines if line.strip()), "")
    expected_title = f"# {stage.title}"
    if not first_nonempty_line.startswith("# Stage "):
        problems.append("Stage markdown must begin with '# Stage '.")
    elif first_nonempty_line != expected_title:
        problems.append(f"Stage markdown title must be exactly '{expected_title}'.")

    for heading in REQUIRED_STAGE_HEADINGS:
        section = extract_markdown_section(markdown, heading)
        if section is None:
            problems.append(f"Missing required section: {heading}")
            continue
        if contains_placeholder_text(section):
            problems.append(f"Section '{heading}' still contains placeholder text.")
        if heading == "Files Produced":
            listed_files = extract_path_references(section)
            if not listed_files:
                problems.append("Section 'Files Produced' must list at least one concrete file path.")
            elif workspace is not None:
                missing = [path for path in listed_files if not _listed_file_exists(workspace.run_root, path)]
                if missing:
                    problems.append(
                        "Section 'Files Produced' references missing file(s): "
                        + ", ".join(f"`{path}`" for path in missing)
                    )
        elif heading == "Decision Ledger":
            required_keywords = (
                "Open Questions",
                "Locked Decisions",
                "Assumptions",
                "Rejected Alternatives",
            )
            if any(keyword not in section for keyword in required_keywords):
                problems.append(
                    "Section 'Decision Ledger' must include Open Questions, Locked Decisions, "
                    "Assumptions, and Rejected Alternatives."
                )

    if stage.slug == "02_hypothesis_generation":
        hypothesis_sections = extract_typed_hypothesis_sections(markdown)
        missing_headings = [heading for heading in TYPED_HYPOTHESIS_HEADINGS if heading not in hypothesis_sections]
        if missing_headings:
            problems.append(
                "Stage 02 'Key Results' must include typed subsections for Theoretical Propositions, "
                "Empirical Hypotheses, and Paper Claims (Provisional)."
            )
        identifier_patterns = {
            "Theoretical Propositions": r"\*\*T\d+\*\*:",
            "Empirical Hypotheses": r"\*\*H\d+\*\*:",
            "Paper Claims (Provisional)": r"\*\*C\d+\*\*:",
        }
        for heading, pattern in identifier_patterns.items():
            section = hypothesis_sections.get(heading)
            if section is not None and not re.search(pattern, section):
                problems.append(f"Stage 02 subsection '{heading}' must include at least one typed identifier.")

    options_section = extract_markdown_section(markdown, "Your Options")
    if options_section is not None:
        if parse_numbered_list_sequence(options_section) != [1, 2, 3, 4, 5, 6]:
            problems.append("Section 'Your Options' must contain exactly options 1-6 in order with no extras.")
        option_items = parse_numbered_list(options_section)
        for index, expected_line in enumerate(FIXED_STAGE_OPTIONS, start=1):
            expected_text = expected_line.split(". ", 1)[1]
            if option_items.get(index) != expected_text:
                problems.append(f"Option {index} in 'Your Options' must be exactly '{expected_text}'.")

    suggestions_section = extract_markdown_section(markdown, "Suggestions for Refinement")
    if suggestions_section is not None:
        if parse_numbered_list_sequence(suggestions_section) != [1, 2, 3]:
            problems.append(
                "Section 'Suggestions for Refinement' must contain exactly suggestions 1-3 in order with no extras."
            )
    try:
        suggestions = parse_refinement_suggestions(markdown)
        if len(suggestions) != 3:
            problems.append("Expected exactly 3 refinement suggestions.")
        for index, suggestion in enumerate(suggestions, start=1):
            if contains_placeholder_text(suggestion):
                problems.append(f"Suggestion {index} still contains placeholder text.")
    except ValueError as exc:
        problems.append(str(exc))

    return StageValidationResult(ok=not problems, errors=tuple(problems))


def _listed_file_exists(run_root: Path, listed_path: str) -> bool:
    normalized = listed_path.strip().strip("`")
    if not normalized:
        return False
    candidate = Path(normalized)
    if candidate.is_absolute():
        return candidate.exists()
    return (run_root / normalized).exists()
