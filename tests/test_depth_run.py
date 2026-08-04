from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from depth_scape.depth_run import DepthRunError, load_depth_run
from depth_scape.image_io import load_image


def _write_depth_run(
    run_dir: Path,
    *,
    image_path: Path,
    depth: np.ndarray,
    artifact_path: str = "relative-depth.npy",
) -> None:
    image = load_image(image_path)
    run_dir.mkdir()
    with (run_dir / artifact_path).open("wb") as stream:
        np.save(stream, depth, allow_pickle=False)
    manifest = {
        "schemaVersion": "0.1",
        "source": {
            "sha256": image.source_sha256,
            "normalizedDimensions": {
                "width": image.width,
                "height": image.height,
            },
        },
        "model": {
            "id": "test/depth",
            "revision": "immutable-test-revision",
        },
        "artifacts": {"relativeDepth": {"path": artifact_path}},
    }
    (run_dir / "run.json").write_text(json.dumps(manifest), encoding="utf-8")


class DepthRunTests(unittest.TestCase):
    def test_loads_only_an_aligned_float32_depth_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_path = root / "input.png"
            run_dir = root / "run"
            Image.new("RGB", (5, 4), (20, 40, 60)).save(image_path)
            depth = np.linspace(0.0, 1.0, 20, dtype=np.float32).reshape(4, 5)
            _write_depth_run(run_dir, image_path=image_path, depth=depth)

            loaded = load_depth_run(run_dir, image=load_image(image_path))

            np.testing.assert_array_equal(loaded.depth, depth)
            self.assertEqual(loaded.depth.dtype, np.float32)
            self.assertEqual(loaded.model_id, "test/depth")
            self.assertEqual(loaded.model_revision, "immutable-test-revision")
            self.assertEqual(len(loaded.depth_sha256), 64)
            self.assertEqual(len(loaded.manifest_sha256), 64)

    def test_rejects_source_mismatch_and_artifact_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_path = root / "input.png"
            other_path = root / "other.png"
            Image.new("RGB", (5, 4), (20, 40, 60)).save(image_path)
            Image.new("RGB", (5, 4), (60, 40, 20)).save(other_path)

            mismatch_dir = root / "mismatch"
            depth = np.linspace(0.0, 1.0, 20, dtype=np.float32).reshape(4, 5)
            _write_depth_run(mismatch_dir, image_path=image_path, depth=depth)
            with self.assertRaisesRegex(DepthRunError, "source hash"):
                load_depth_run(mismatch_dir, image=load_image(other_path))

            escaped_dir = root / "escaped"
            _write_depth_run(escaped_dir, image_path=image_path, depth=depth)
            manifest_path = escaped_dir / "run.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["relativeDepth"]["path"] = "../outside.npy"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(DepthRunError, "escapes"):
                load_depth_run(escaped_dir, image=load_image(image_path))

    def test_rejects_wrong_shape_dtype_range_and_npz_container(self) -> None:
        invalid_depths = (
            np.zeros((5, 4), dtype=np.float32),
            np.zeros((4, 5), dtype=np.float64),
            np.full((4, 5), 1.1, dtype=np.float32),
        )
        for index, depth in enumerate(invalid_depths):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                image_path = root / "input.png"
                run_dir = root / "run"
                Image.new("RGB", (5, 4)).save(image_path)
                _write_depth_run(run_dir, image_path=image_path, depth=depth)
                with self.assertRaises(DepthRunError):
                    load_depth_run(run_dir, image=load_image(image_path))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_path = root / "input.png"
            run_dir = root / "run"
            Image.new("RGB", (5, 4)).save(image_path)
            image = load_image(image_path)
            run_dir.mkdir()
            np.savez(run_dir / "relative-depth.npy", depth=np.zeros((4, 5), np.float32))
            manifest = {
                "schemaVersion": "0.1",
                "source": {
                    "sha256": image.source_sha256,
                    "normalizedDimensions": {"width": 5, "height": 4},
                },
                "model": {"id": "test/depth", "revision": "test-revision"},
                "artifacts": {
                    "relativeDepth": {"path": "relative-depth.npy.npz"},
                },
            }
            (run_dir / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(DepthRunError, "single NumPy NPY"):
                load_depth_run(run_dir, image=image)


if __name__ == "__main__":
    unittest.main()
