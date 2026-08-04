from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from depth_scape.image_io import load_image
from depth_scape.mesh import MeshBuildConfig
from depth_scape.mesh_artifacts import MeshArtifactError
from depth_scape.mesh_baseline import run_mesh_baseline


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_test_input(root: Path) -> tuple[Path, Path, np.ndarray]:
    input_path = root / "input.png"
    depth_run_dir = root / "depth-run"
    image_array = np.zeros((9, 12, 3), dtype=np.uint8)
    image_array[:, :6] = (40, 80, 180)
    image_array[:, 6:] = (180, 140, 60)
    Image.fromarray(image_array).save(input_path)
    image = load_image(input_path)

    depth_run_dir.mkdir()
    depth = np.full((9, 12), 0.1, dtype=np.float32)
    depth[:, 6:] = 0.8
    depth_path = depth_run_dir / "relative-depth.npy"
    with depth_path.open("wb") as stream:
        np.save(stream, depth, allow_pickle=False)
    manifest = {
        "schemaVersion": "0.1",
        "source": {
            "sha256": image.source_sha256,
            "normalizedDimensions": {"width": 12, "height": 9},
        },
        "model": {
            "id": "test/depth",
            "revision": "immutable-test-revision",
        },
        "artifacts": {"relativeDepth": {"path": depth_path.name}},
    }
    (depth_run_dir / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    return input_path, depth_run_dir, image_array


class MeshBaselineArtifactTests(unittest.TestCase):
    def test_writes_observed_texture_mesh_arrays_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path, depth_run_dir, source = _write_test_input(root)
            output_dir = root / "mesh"

            artifacts = run_mesh_baseline(
                input_path=input_path,
                depth_run_dir=depth_run_dir,
                output_dir=output_dir,
                config=MeshBuildConfig(
                    max_mesh_dimension=12,
                    depth_jump_threshold=0.2,
                ),
            )

            with Image.open(artifacts.texture) as opened:
                texture = np.asarray(opened).copy()
                self.assertEqual(opened.mode, "RGB")
            with Image.open(artifacts.cut_cells) as opened:
                cut_cells = np.asarray(opened).copy()
                self.assertEqual(opened.mode, "L")
            with Image.open(artifacts.preview) as opened:
                preview = np.asarray(opened).copy()
                self.assertEqual(opened.size, (12, 9))
            vertices = np.load(artifacts.vertices, allow_pickle=False)
            uv = np.load(artifacts.texture_coordinates, allow_pickle=False)
            faces = np.load(artifacts.faces, allow_pickle=False)
            manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))

            np.testing.assert_array_equal(texture, source)
            self.assertTrue(np.any(preview != source))
            self.assertTrue(np.any(cut_cells == 255))
            self.assertEqual(vertices.dtype, np.float32)
            self.assertEqual(uv.dtype, np.float32)
            self.assertEqual(faces.dtype, np.int32)
            self.assertEqual(vertices.shape[1], 3)
            self.assertEqual(uv.shape[1], 2)
            self.assertEqual(faces.shape[1], 3)
            self.assertEqual(manifest["source"]["provenance"], "observed")
            self.assertEqual(manifest["depthInput"]["provenance"], "inferred")
            self.assertTrue(manifest["algorithm"]["result"]["defaultTexturePixelIdentical"])
            self.assertEqual(
                manifest["artifacts"]["vertices"]["sha256"],
                _sha256(artifacts.vertices),
            )
            self.assertTrue(
                any("not deleted source pixels" in item for item in manifest["warnings"])
            )

            with self.assertRaises(MeshArtifactError):
                run_mesh_baseline(
                    input_path=input_path,
                    depth_run_dir=depth_run_dir,
                    output_dir=output_dir,
                )


if __name__ == "__main__":
    unittest.main()
