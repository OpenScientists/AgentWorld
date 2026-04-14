from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agentworld import AgentGraph, DefaultOperator, StaticController
from agentworld.controller.base import ControllerEvent
from agentworld.skill_loader import load_skill, load_skills


class SkillLoaderTests(unittest.TestCase):
    def test_load_skill_reads_frontmatter_and_supporting_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "skills" / "demo-skill"
            (skill_dir / "references").mkdir(parents=True)
            (skill_dir / "scripts").mkdir(parents=True)
            (skill_dir / "assets").mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: demo-skill\n"
                "description: Demo skill for testing.\n"
                "---\n\n"
                "# Demo Skill\n\n"
                "## Workflow\n"
                "1. First\n"
                "2. Second\n",
                encoding="utf-8",
            )
            (skill_dir / "references" / "guide.md").write_text("reference", encoding="utf-8")
            (skill_dir / "scripts" / "run.sh").write_text("echo test\n", encoding="utf-8")
            (skill_dir / "assets" / "template.txt").write_text("template", encoding="utf-8")

            loaded = load_skill("demo-skill", working_dir=root)

            self.assertEqual(loaded.name, "demo-skill")
            self.assertEqual(loaded.description, "Demo skill for testing.")
            self.assertIn("# Demo Skill", loaded.content)
            self.assertEqual(loaded.references, ["references/guide.md"])
            self.assertEqual(loaded.scripts, ["scripts/run.sh"])
            self.assertEqual(loaded.assets, ["assets/template.txt"])

    def test_operator_instruction_contains_loaded_skill_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "skills" / "demo-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: demo-skill\n"
                "description: Demo skill for instruction injection.\n"
                "---\n\n"
                "# Demo Skill\n\n"
                "Use this skill to validate that the operator injects real skill content.\n",
                encoding="utf-8",
            )

            def script(request):
                payload = json.loads(request.instruction)
                loaded_skills = payload["loaded_skills"]
                return [
                    ControllerEvent(
                        kind="completed",
                        payload={
                            "state_patch": {
                                "loaded_skill_name": loaded_skills[0]["name"],
                                "loaded_skill_description": loaded_skills[0]["description"],
                                "loaded_skill_has_content": "operator injects real skill content"
                                in loaded_skills[0]["content"],
                            }
                        },
                    )
                ]

            graph = AgentGraph(name="skill-instruction")
            graph.add_operator("demo_op", DefaultOperator("demo_op", StaticController(script)))
            graph.add_node("demo", operator="demo_op", skills=["demo-skill"])

            result = graph.compile().invoke({}, working_dir=root)

            self.assertEqual(result.status, "success")
            self.assertEqual(result.state["loaded_skill_name"], "demo-skill")
            self.assertEqual(result.state["loaded_skill_description"], "Demo skill for instruction injection.")
            self.assertTrue(result.state["loaded_skill_has_content"])

    def test_load_skills_preserves_order_and_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("first", "second"):
                skill_dir = root / "skills" / name
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: {name}\n---\n\n# {name}\n",
                    encoding="utf-8",
                )

            loaded = load_skills(["first", "second", "first"], working_dir=root)

            self.assertEqual([skill.name for skill in loaded], ["first", "second"])


if __name__ == "__main__":
    unittest.main()
