from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agentworld.workspace import create_run_workspace


class WorkspacePrimitiveTests(unittest.TestCase):
    def test_create_run_workspace_materializes_expected_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = create_run_workspace(
                runs_dir=Path(tmp),
                run_id="demo-run",
                goal="Build a research workflow.",
                config={"operator": "demo"},
            )

            self.assertEqual(paths.run_root.name, "demo-run")
            self.assertTrue(paths.goal.exists())
            self.assertTrue(paths.user_input.exists())
            self.assertTrue(paths.memory.exists())
            self.assertTrue(paths.prompt_cache_dir.is_dir())
            self.assertTrue(paths.operator_state_dir.is_dir())
            self.assertTrue(paths.stages_dir.is_dir())
            self.assertTrue(paths.logs_raw_dir.is_dir())
            self.assertTrue(paths.workspace_root.is_dir())
            self.assertTrue(paths.literature_dir.is_dir())
            self.assertTrue(paths.results_dir.is_dir())
            self.assertTrue(paths.bootstrap_dir.is_dir())
            self.assertEqual(paths.experiment_manifest.name, "experiment_manifest.json")

            config = json.loads(paths.run_config.read_text(encoding="utf-8"))
            self.assertEqual(config["operator"], "demo")
            self.assertEqual(config["run_id"], "demo-run")


if __name__ == "__main__":
    unittest.main()
