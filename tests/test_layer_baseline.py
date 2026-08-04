from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from depth_scape.image_io import load_image
from depth_scape.layer_artifacts import LayerArtifactError
from depth_scape.layer_baseline import run_layer_baseline


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_test_input(root: Path) -> tuple[Path, Path]:
    input_path = root / "input.png"
    depth_run_dir = root / "depth-run"
    image_array = np.zeros((9, 12, 3), dtype=np.uint8)
    image_array[:3] = (40, 80, 180)
    image_array[3:6] = (120, 130, 100)
    image_array[6:] = (80, 60, 40)
    Image.fromarray(image_array).save(input_path)
    image = load_image(input_path)

    depth_run_dir.mkdir()
    depth = np.vstack(
        (
            np.full((3, 12), 0.1, dtype=np.float32),
            np.full((3, 12), 0.5, dtype=np.float32),
            np.full((3, 12), 0.9, dtype=np.float32),
        )
    )
    with (depth_run_dir / "relative-depth.npy").open("wb") as stream:
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
        "artifacts": {"relativeDepth": {"path": "relative-depth.npy"}},
    }
    (depth_run_dir / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    return input_path, depth_run_dir


class LayerBaselineArtifactTests(unittest.TestCase):
    def test_writes_aligned_exhaustive_masks_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path, depth_run_dir = _write_test_input(root)
            output_dir = root / "layers"

            artifacts = run_layer_baseline(
                input_path=input_path,
                depth_run_dir=depth_run_dir,
                output_dir=output_dir,
            )

            labels = np.load(artifacts.layer_map, allow_pickle=False)
            layer_depth = np.load(artifacts.refined_depth, allow_pickle=False)
            boundary = np.load(artifacts.boundary_strength, allow_pickle=False)
            masks = []
            for path in (
                artifacts.background_mask,
                artifacts.midground_mask,
                artifacts.foreground_mask,
            ):
                with Image.open(path) as opened:
                    masks.append(np.asarray(opened).copy())
            with Image.open(artifacts.preview) as preview:
                self.assertEqual(preview.mode, "RGB")
                self.assertEqual(preview.size, (12, 9))
            manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))

            self.assertEqual(labels.shape, (9, 12))
            self.assertEqual(labels.dtype, np.uint8)
            self.assertEqual(layer_depth.dtype, np.float32)
            self.assertEqual(boundary.dtype, np.float32)
            np.testing.assert_array_equal(sum(masks), np.full((9, 12), 255))
            for label, mask in enumerate(masks):
                np.testing.assert_array_equal(mask == 255, labels == label)
            self.assertEqual(manifest["source"]["provenance"], "observed")
            self.assertEqual(manifest["depthInput"]["provenance"], "inferred")
            self.assertEqual(manifest["artifacts"]["layerMap"]["provenance"], "inferred")
            self.assertEqual(manifest["artifacts"]["layerMap"]["shape"], [9, 12])
            self.assertEqual(
                manifest["artifacts"]["layerMap"]["sha256"],
                _sha256(artifacts.layer_map),
            )
            self.assertAlmostEqual(
                sum(manifest["algorithm"]["result"]["fractionsFarToNear"]),
                1.0,
            )

            with self.assertRaises(LayerArtifactError):
                run_layer_baseline(
                    input_path=input_path,
                    depth_run_dir=depth_run_dir,
                    output_dir=output_dir,
                )


if __name__ == "__main__":
    unittest.main()
