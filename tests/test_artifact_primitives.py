from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentworld.artifacts import ArtifactRequirement, scan_artifacts, validate_artifact_requirements


class ArtifactPrimitiveTests(unittest.TestCase):
    def test_scan_and_validate_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            (workspace / "results").mkdir(parents=True)
            (workspace / "results" / "metrics.json").write_text('{"score": 1.0}\n', encoding="utf-8")

            index = scan_artifacts(workspace)

            self.assertEqual(index.artifact_count, 1)
            self.assertEqual(index.artifacts[0].category, "results")
            self.assertEqual(index.artifacts[0].relative_path, "results/metrics.json")
            self.assertEqual(index.artifacts[0].schema["kind"], "object")

            validation = validate_artifact_requirements(
                run_root=root,
                requirements=[
                    ArtifactRequirement("workspace/results/metrics.json"),
                    ArtifactRequirement("workspace/results/missing.json"),
                ],
            )

            self.assertFalse(validation.ok)
            self.assertEqual(validation.present, ("workspace/results/metrics.json",))
            self.assertEqual(validation.missing, ("workspace/results/missing.json",))


if __name__ == "__main__":
    unittest.main()
