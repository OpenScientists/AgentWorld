from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..stage.markdown import (
    TYPED_HYPOTHESIS_HEADINGS,
    TYPED_HYPOTHESIS_IDENTIFIER_PATTERNS,
    extract_typed_hypothesis_sections,
)
from ..utils import utc_now
from ..workspace import RunWorkspace


@dataclass(frozen=True, slots=True)
class HypothesisEntry:
    identifier: str
    statement: str
    claim_type: str
    derived_from: str = ""
    depends_on: str = ""
    verification_needed: str = ""
    status: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.identifier,
            "type": self.claim_type,
            "statement": self.statement,
            "derived_from": self.derived_from,
            "depends_on": self.depends_on,
            "verification_needed": self.verification_needed,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "HypothesisEntry":
        return cls(
            identifier=str(payload.get("id") or "").strip(),
            claim_type=str(payload.get("type") or "").strip(),
            statement=str(payload.get("statement") or "").strip(),
            derived_from=str(payload.get("derived_from") or "").strip(),
            depends_on=str(payload.get("depends_on") or "").strip(),
            verification_needed=str(payload.get("verification_needed") or "").strip(),
            status=str(payload.get("status") or "").strip(),
        )


@dataclass(frozen=True, slots=True)
class HypothesisManifest:
    generated_at: str
    theoretical_propositions: tuple[HypothesisEntry, ...]
    empirical_hypotheses: tuple[HypothesisEntry, ...]
    paper_claims: tuple[HypothesisEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "theoretical_propositions": [entry.to_dict() for entry in self.theoretical_propositions],
            "empirical_hypotheses": [entry.to_dict() for entry in self.empirical_hypotheses],
            "paper_claims": [entry.to_dict() for entry in self.paper_claims],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "HypothesisManifest":
        return cls(
            generated_at=str(payload.get("generated_at") or "").strip(),
            theoretical_propositions=tuple(
                HypothesisEntry.from_dict(item)
                for item in payload.get("theoretical_propositions", [])
                if isinstance(item, dict)
            ),
            empirical_hypotheses=tuple(
                HypothesisEntry.from_dict(item)
                for item in payload.get("empirical_hypotheses", [])
                if isinstance(item, dict)
            ),
            paper_claims=tuple(
                HypothesisEntry.from_dict(item)
                for item in payload.get("paper_claims", [])
                if isinstance(item, dict)
            ),
        )


def build_hypothesis_manifest(stage_markdown: str) -> HypothesisManifest | None:
    sections = extract_typed_hypothesis_sections(stage_markdown)
    if len(sections) < len(TYPED_HYPOTHESIS_HEADINGS):
        return None
    manifest = HypothesisManifest(
        generated_at=utc_now(),
        theoretical_propositions=_parse_section(sections["Theoretical Propositions"], "theoretical_proposition"),
        empirical_hypotheses=_parse_section(sections["Empirical Hypotheses"], "empirical_hypothesis"),
        paper_claims=_parse_section(sections["Paper Claims (Provisional)"], "paper_claim"),
    )
    if not (manifest.theoretical_propositions or manifest.empirical_hypotheses or manifest.paper_claims):
        return None
    return manifest


def write_hypothesis_manifest(workspace: RunWorkspace, stage_markdown: str) -> HypothesisManifest | None:
    manifest = build_hypothesis_manifest(stage_markdown)
    if manifest is None:
        return None
    workspace.hypothesis_manifest.parent.mkdir(parents=True, exist_ok=True)
    workspace.hypothesis_manifest.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_hypothesis_manifest(path: Path) -> HypothesisManifest | None:
    if not path.exists():
        return None
    return HypothesisManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))


def format_hypothesis_manifest_for_prompt(manifest: HypothesisManifest) -> str:
    lines: list[str] = []
    groups = (
        ("Theoretical Propositions", manifest.theoretical_propositions),
        ("Empirical Hypotheses", manifest.empirical_hypotheses),
        ("Paper Claims (Provisional)", manifest.paper_claims),
    )
    for heading, entries in groups:
        if not entries:
            continue
        lines.append(f"### {heading}")
        for item in entries:
            lines.append(f"- **{item.identifier}**: {item.statement}")
            if item.derived_from:
                lines.append(f"  - Derived from: {item.derived_from}")
            if item.depends_on:
                lines.append(f"  - Depends on: {item.depends_on}")
            if item.verification_needed:
                lines.append(f"  - Verification: {item.verification_needed}")
            if item.status:
                lines.append(f"  - Status: {item.status}")
        lines.append("")
    return "\n".join(lines).strip()


def _parse_section(section_text: str, claim_type: str) -> tuple[HypothesisEntry, ...]:
    entries: list[HypothesisEntry] = []
    seen: set[str] = set()
    current: dict[str, str] | None = None
    identifier_pattern = _identifier_pattern_for_type(claim_type)
    for raw_line in section_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        entry_match = re.match(
            rf"^-\s+(?:\*\*)?({identifier_pattern})(?:\*\*)?\s*[:\-]\s*(.+)$",
            stripped,
            flags=re.IGNORECASE,
        )
        if entry_match:
            if current is not None:
                _append_entry(entries, seen, current, claim_type)
            current = {"id": _normalize_identifier(entry_match.group(1)), "statement": entry_match.group(2).strip()}
            continue
        if current is None:
            continue
        detail_match = re.match(r"^-\s+([^:]+):\s*(.+)$", stripped)
        if detail_match:
            label = detail_match.group(1).strip().lower()
            value = detail_match.group(2).strip()
            if label == "derived from":
                current["derived_from"] = value
            elif label == "depends on":
                current["depends_on"] = value
            elif label == "verification":
                current["verification_needed"] = value
            elif label == "status":
                current["status"] = value
    if current is not None:
        _append_entry(entries, seen, current, claim_type)

    for table_entry in _parse_table_entries(section_text, claim_type):
        if table_entry.identifier not in seen:
            seen.add(table_entry.identifier)
            entries.append(table_entry)
    return tuple(entries)


def _parse_table_entries(section_text: str, claim_type: str) -> tuple[HypothesisEntry, ...]:
    entries: list[HypothesisEntry] = []
    identifier_pattern = _identifier_pattern_for_type(claim_type)
    headers: list[str] = []
    for raw_line in section_text.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [_clean_table_cell(cell) for cell in stripped.strip("|").split("|")]
        if not cells or _is_separator_row(cells):
            continue
        first = cells[0].lower()
        if first in {"id", "identifier", "claim id", "hypothesis id"}:
            headers = [_normalize_header(cell) for cell in cells]
            continue
        identifier_match = re.search(identifier_pattern, cells[0], flags=re.IGNORECASE)
        if identifier_match is None:
            continue
        identifier = _normalize_identifier(identifier_match.group(0))
        row = _row_by_header(headers, cells)
        statement = _first_nonempty(
            row.get("statement"),
            _join_nonempty(row.get("title"), row.get("prediction")),
            row.get("title"),
            _join_nonempty(*cells[1:3]),
        )
        if not statement:
            continue
        entries.append(
            HypothesisEntry(
                identifier=identifier,
                statement=statement,
                claim_type=claim_type,
                derived_from=_first_nonempty(
                    row.get("derived from"),
                    row.get("source"),
                    row.get("sources"),
                    row.get("source claims"),
                    row.get("source claim ids"),
                ),
                depends_on=_first_nonempty(row.get("depends on"), row.get("dependency")),
                verification_needed=_first_nonempty(
                    row.get("verification"),
                    row.get("falsification"),
                    row.get("falsification criterion"),
                    row.get("experiment"),
                    row.get("experiment action"),
                    row.get("metric"),
                ),
                status=_first_nonempty(row.get("status"), _status_from_confidence(row.get("confidence"))),
            )
        )
    return tuple(entries)


def _append_entry(
    entries: list[HypothesisEntry],
    seen: set[str],
    state: dict[str, str],
    claim_type: str,
) -> None:
    entry = _entry_from_state(state, claim_type)
    if not entry.identifier or entry.identifier in seen:
        return
    seen.add(entry.identifier)
    entries.append(entry)


def _entry_from_state(state: dict[str, str], claim_type: str) -> HypothesisEntry:
    return HypothesisEntry(
        identifier=state.get("id", ""),
        statement=state.get("statement", ""),
        claim_type=claim_type,
        derived_from=state.get("derived_from", ""),
        depends_on=state.get("depends_on", ""),
        verification_needed=state.get("verification_needed", ""),
        status=state.get("status", ""),
    )


def _identifier_pattern_for_type(claim_type: str) -> str:
    if claim_type == "theoretical_proposition":
        return TYPED_HYPOTHESIS_IDENTIFIER_PATTERNS["Theoretical Propositions"]
    if claim_type == "empirical_hypothesis":
        return TYPED_HYPOTHESIS_IDENTIFIER_PATTERNS["Empirical Hypotheses"]
    if claim_type == "paper_claim":
        return TYPED_HYPOTHESIS_IDENTIFIER_PATTERNS["Paper Claims (Provisional)"]
    return r"(?<![A-Z0-9])(?:TH-\d+|EH-\d+|PC-\d+|T\d+|H\d+|C\d+)(?![A-Z0-9])"


def _normalize_identifier(identifier: str) -> str:
    return re.sub(r"\s+", "", identifier.strip().upper())


def _clean_table_cell(cell: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", cell, flags=re.IGNORECASE)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return " ".join(text.split())


def _normalize_header(header: str) -> str:
    return _clean_table_cell(header).strip().lower().replace("_", " ")


def _is_separator_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells if cell.strip())


def _row_by_header(headers: list[str], cells: list[str]) -> dict[str, str]:
    if not headers:
        return {}
    return {header: cells[index] for index, header in enumerate(headers) if index < len(cells)}


def _first_nonempty(*values: str | None) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _join_nonempty(*values: str | None) -> str:
    return ". ".join(value.strip() for value in values if value and value.strip())


def _status_from_confidence(confidence: str | None) -> str:
    if not confidence:
        return ""
    return f"confidence: {confidence.strip()}"
