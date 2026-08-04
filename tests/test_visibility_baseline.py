from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from test_layer_run import write_layer_run

from depth_scape.visibility import VisibilityConfig
from depth_scape.visibility_artifacts import VisibilityArtifactError
from depth_scape.visibility_baseline import run_visibility_baseline


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class VisibilityBaselineTests(unittest.TestCase):
    def test_writes_camera_plan_masks_and_reproducibility_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layer_run_dir = root / "layers"
            output_dir = root / "camera"
            labels = np.zeros((6, 20), dtype=np.uint8)
            labels[:, 5:15] = 1
            labels[:, 8:12] = 2
            write_layer_run(layer_run_dir, labels=labels)

            artifacts = run_visibility_baseline(
                layer_run_dir=layer_run_dir,
                output_dir=output_dir,
                config=VisibilityConfig(max_foreground_shift_fraction=0.1),
            )

            with Image.open(artifacts.background_disocclusion) as opened:
                background = np.asarray(opened).copy()
                self.assertEqual(opened.mode, "L")
            with Image.open(artifacts.midground_disocclusion) as opened:
                midground = np.asarray(opened).copy()
            with Image.open(artifacts.all_view_holes) as opened:
                all_holes = np.asarray(opened).copy()
            with Image.open(artifacts.preview) as opened:
                self.assertEqual(opened.mode, "RGB")
                self.assertEqual(opened.size, (20, 6))
            manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))

            self.assertTrue(np.any(background == 255))
            self.assertTrue(np.any(midground == 255))
            np.testing.assert_array_equal(background, all_holes)
            self.assertEqual(manifest["camera"]["positionRange"], [-1.0, 1.0])
            self.assertEqual(manifest["camera"]["defaultPosition"], 0.0)
            self.assertEqual(manifest["camera"]["maxForegroundShiftPixelsApplied"], 2)
            self.assertEqual(manifest["camera"]["sampledPositions"], 5)
            self.assertEqual(manifest["layerInput"]["provenance"], "inferred")
            self.assertEqual(
                manifest["artifacts"]["backgroundDisocclusionMask"]["sha256"],
                _sha256(artifacts.background_disocclusion),
            )
            self.assertTrue(
                any("not a physical camera model" in warning for warning in manifest["warnings"])
            )

            with self.assertRaises(VisibilityArtifactError):
                run_visibility_baseline(
                    layer_run_dir=layer_run_dir,
                    output_dir=output_dir,
                    config=VisibilityConfig(max_foreground_shift_fraction=0.1),
                )


if __name__ == "__main__":
    unittest.main()
