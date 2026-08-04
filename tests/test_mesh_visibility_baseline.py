from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from test_mesh_baseline import _write_test_input

from depth_scape.mesh import MeshBuildConfig
from depth_scape.mesh_baseline import run_mesh_baseline
from depth_scape.mesh_visibility import MeshVisibilityConfig
from depth_scape.mesh_visibility_artifacts import MeshVisibilityArtifactError
from depth_scape.mesh_visibility_baseline import run_mesh_visibility_baseline


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MeshVisibilityBaselineTests(unittest.TestCase):
    def test_writes_views_hole_masks_and_reproducibility_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path, depth_run_dir, source = _write_test_input(root)
            mesh_dir = root / "mesh"
            output_dir = root / "mesh-camera"
            run_mesh_baseline(
                input_path=input_path,
                depth_run_dir=depth_run_dir,
                output_dir=mesh_dir,
                config=MeshBuildConfig(max_mesh_dimension=12, depth_jump_threshold=0.2),
            )

            artifacts = run_mesh_visibility_baseline(
                mesh_run_dir=mesh_dir,
                output_dir=output_dir,
                config=MeshVisibilityConfig(
                    max_render_dimension=12,
                    max_near_shift_fraction=0.1,
                ),
            )

            with Image.open(artifacts.center_view) as opened:
                center = np.asarray(opened).copy()
                self.assertEqual(opened.mode, "RGB")
            with Image.open(artifacts.left_view_holes) as opened:
                left_holes = np.asarray(opened).copy()
                self.assertEqual(opened.mode, "L")
            with Image.open(artifacts.all_view_holes) as opened:
                all_holes = np.asarray(opened).copy()
            manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))

            np.testing.assert_array_equal(center, source)
            self.assertTrue(np.any(left_holes == 255))
            self.assertTrue(np.any(all_holes == 255))
            self.assertEqual(manifest["camera"]["positionRange"], [-1.0, 1.0])
            self.assertEqual(manifest["camera"]["sampledPositions"], [-1.0, 0.0, 1.0])
            self.assertTrue(manifest["result"]["defaultViewPixelIdenticalAtRenderResolution"])
            self.assertEqual(
                manifest["artifacts"]["allViewHoles"]["sha256"],
                _sha256(artifacts.all_view_holes),
            )
            self.assertTrue(any("not recover hidden" in item for item in manifest["warnings"]))

            with self.assertRaises(MeshVisibilityArtifactError):
                run_mesh_visibility_baseline(
                    mesh_run_dir=mesh_dir,
                    output_dir=output_dir,
                )


if __name__ == "__main__":
    unittest.main()
