from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from test_mesh_baseline import _write_test_input

from depth_scape.mesh import MeshBuildConfig
from depth_scape.mesh_baseline import run_mesh_baseline
from depth_scape.mesh_run import MeshRunError, load_mesh_run


class MeshRunTests(unittest.TestCase):
    def test_loads_validated_texture_geometry_and_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path, depth_run_dir, source = _write_test_input(root)
            mesh_dir = root / "mesh"
            run_mesh_baseline(
                input_path=input_path,
                depth_run_dir=depth_run_dir,
                output_dir=mesh_dir,
                config=MeshBuildConfig(max_mesh_dimension=12, depth_jump_threshold=0.2),
            )

            loaded = load_mesh_run(mesh_dir)

            np.testing.assert_array_equal(loaded.texture, source)
            self.assertEqual(loaded.vertices.dtype, np.float32)
            self.assertEqual(loaded.texture_coordinates.dtype, np.float32)
            self.assertEqual(loaded.faces.dtype, np.int32)
            self.assertEqual(loaded.width, 12)
            self.assertEqual(loaded.height, 9)
            self.assertEqual(loaded.algorithm_id, "continuous-depth-grid-cut")
            self.assertEqual(len(loaded.manifest_sha256), 64)

    def test_rejects_escaped_paths_and_changed_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path, depth_run_dir, _ = _write_test_input(root)
            mesh_dir = root / "mesh"
            artifacts = run_mesh_baseline(
                input_path=input_path,
                depth_run_dir=depth_run_dir,
                output_dir=mesh_dir,
                config=MeshBuildConfig(max_mesh_dimension=12, depth_jump_threshold=0.2),
            )
            manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))
            manifest["artifacts"]["vertices"]["path"] = "../outside.npy"
            artifacts.manifest.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(MeshRunError, "escapes"):
                load_mesh_run(mesh_dir)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path, depth_run_dir, _ = _write_test_input(root)
            mesh_dir = root / "mesh"
            artifacts = run_mesh_baseline(
                input_path=input_path,
                depth_run_dir=depth_run_dir,
                output_dir=mesh_dir,
                config=MeshBuildConfig(max_mesh_dimension=12, depth_jump_threshold=0.2),
            )
            vertices = np.load(artifacts.vertices, allow_pickle=False)
            vertices[0, 2] += np.float32(0.01)
            with artifacts.vertices.open("wb") as stream:
                np.save(stream, vertices, allow_pickle=False)
            with self.assertRaisesRegex(MeshRunError, "hash"):
                load_mesh_run(mesh_dir)


if __name__ == "__main__":
    unittest.main()
