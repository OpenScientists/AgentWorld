from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(slots=True)
class LoadedSkill:
    requested_name: str
    name: str
    description: str
    root: Path
    skill_file: Path
    content: str
    references: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_name": self.requested_name,
            "name": self.name,
            "description": self.description,
            "root": str(self.root),
            "skill_file": str(self.skill_file),
            "content": self.content,
            "references": list(self.references),
            "scripts": list(self.scripts),
            "assets": list(self.assets),
        }


def load_skills(skill_names: Iterable[str], *, working_dir: Path | None = None) -> list[LoadedSkill]:
    base_dir = (working_dir or Path.cwd()).resolve()
    loaded: list[LoadedSkill] = []
    seen: set[str] = set()
    for raw_name in skill_names:
        name = str(raw_name).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        loaded.append(load_skill(name, working_dir=base_dir))
    return loaded


def load_skill(skill_name: str, *, working_dir: Path | None = None) -> LoadedSkill:
    base_dir = (working_dir or Path.cwd()).resolve()
    skill_dir = _find_skill_dir(base_dir, skill_name)
    skill_file = skill_dir / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")
    header, body = _split_frontmatter(text)
    return LoadedSkill(
        requested_name=skill_name,
        name=str(header.get("name") or skill_name),
        description=str(header.get("description") or ""),
        root=skill_dir,
        skill_file=skill_file,
        content=body.strip(),
        references=_list_relative_files(skill_dir / "references"),
        scripts=_list_relative_files(skill_dir / "scripts"),
        assets=_list_relative_files(skill_dir / "assets"),
    )


def _find_skill_dir(start_dir: Path, skill_name: str) -> Path:
    for current in (start_dir, *start_dir.parents):
        candidate = current / "skills" / skill_name
        if (candidate / "SKILL.md").is_file():
            return candidate
    raise FileNotFoundError(f"Skill not found: {skill_name}")


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text

    lines = text.splitlines()
    header_lines: list[str] = []
    end_index: int | None = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = idx
            break
        header_lines.append(line)

    if end_index is None:
        return {}, text

    header: dict[str, str] = {}
    for line in header_lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and not value.startswith(("[", "{")):
            header[key] = value

    body = "\n".join(lines[end_index + 1 :])
    return header, body


def _list_relative_files(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(
        str(path.relative_to(directory.parent))
        for path in directory.rglob("*")
        if path.is_file()
    )
