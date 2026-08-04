from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from depth_scape.artifacts import ArtifactWriteError
from depth_scape.baseline import run_depth_baseline
from depth_scape.contracts import DepthPrediction, InferenceTelemetry, ModelIdentity


class FakeEstimator:
    def predict(self, image: Image.Image, *, seed: int) -> DepthPrediction:
        values = np.arange(image.height * image.width, dtype=np.float32).reshape(
            image.height,
            image.width,
        )
        return DepthPrediction(
            values=values,
            model=ModelIdentity(
                model_id="test/depth",
                revision="immutable-test-revision",
                backend="fake",
                upstream_code_license="MIT",
                weights_license="MIT",
                backend_code_license="MIT",
                weights_sha256="0" * 64,
                weights_bytes=1,
                source_url="https://example.invalid/test/depth",
            ),
            telemetry=InferenceTelemetry(
                device="cpu",
                device_name="CPU",
                precision="float32",
                model_load_seconds=0.0,
                inference_seconds=0.0,
                peak_accelerator_memory_bytes=None,
                package_versions={"fake": "1.0"},
            ),
        )


class BaselineArtifactTests(unittest.TestCase):
    def test_writes_aligned_depth_preview_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.png"
            output_dir = root / "run"
            Image.new("RGB", (6, 4), (20, 40, 60)).save(input_path)

            artifacts = run_depth_baseline(
                input_path=input_path,
                output_dir=output_dir,
                estimator=FakeEstimator(),
                seed=7,
            )

            depth = np.load(artifacts.depth, allow_pickle=False)
            with Image.open(artifacts.preview) as preview:
                self.assertEqual(preview.size, (6, 4))
                self.assertEqual(preview.mode, "L")
            manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))

            self.assertEqual(depth.shape, (4, 6))
            self.assertEqual(depth.dtype, np.float32)
            self.assertEqual(float(depth.min()), 0.0)
            self.assertEqual(float(depth.max()), 1.0)
            self.assertEqual(manifest["source"]["provenance"], "observed")
            self.assertEqual(
                manifest["artifacts"]["relativeDepth"]["provenance"],
                "inferred",
            )
            self.assertEqual(
                manifest["artifacts"]["relativeDepth"]["shape"],
                [4, 6],
            )
            self.assertEqual(manifest["configuration"]["seed"], 7)
            self.assertEqual(manifest["software"]["depthScape"]["version"], "0.1.0")
            self.assertEqual(manifest["model"]["licenses"]["weights"], "MIT")

            with self.assertRaises(ArtifactWriteError):
                run_depth_baseline(
                    input_path=input_path,
                    output_dir=output_dir,
                    estimator=FakeEstimator(),
                )


if __name__ == "__main__":
    unittest.main()
