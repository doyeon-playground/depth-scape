from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from depth_scape.layer_run import LayerRunError, load_layer_run


def write_layer_run(
    run_dir: Path,
    *,
    labels: np.ndarray,
    source_sha256: str = "a" * 64,
    artifact_path: str = "layer-map.npy",
) -> None:
    run_dir.mkdir()
    artifact = run_dir / artifact_path
    with artifact.open("wb") as stream:
        np.save(stream, labels, allow_pickle=False)
    manifest = {
        "schemaVersion": "0.1",
        "source": {
            "sha256": source_sha256,
            "dimensions": {
                "width": int(labels.shape[1]),
                "height": int(labels.shape[0]),
            },
        },
        "algorithm": {
            "id": "test/layers",
            "version": "test-version",
        },
        "artifacts": {
            "layerMap": {
                "path": artifact_path,
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            }
        },
    }
    (run_dir / "layers.json").write_text(json.dumps(manifest), encoding="utf-8")


class LayerRunTests(unittest.TestCase):
    def test_loads_a_validated_three_layer_map(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "layers"
            labels = np.tile(np.array([0, 1, 2], dtype=np.uint8), (4, 1))
            write_layer_run(run_dir, labels=labels)

            loaded = load_layer_run(run_dir)

            np.testing.assert_array_equal(loaded.labels, labels)
            self.assertEqual((loaded.width, loaded.height), (3, 4))
            self.assertEqual(loaded.source_sha256, "a" * 64)
            self.assertEqual(loaded.algorithm_id, "test/layers")
            self.assertEqual(loaded.algorithm_version, "test-version")
            self.assertEqual(len(loaded.layer_map_sha256), 64)
            self.assertEqual(len(loaded.manifest_sha256), 64)

    def test_rejects_hash_mismatch_path_escape_and_invalid_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            labels = np.tile(np.array([0, 1, 2], dtype=np.uint8), (4, 1))

            hash_dir = root / "hash"
            write_layer_run(hash_dir, labels=labels)
            manifest_path = hash_dir / "layers.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["layerMap"]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(LayerRunError, "SHA-256"):
                load_layer_run(hash_dir)

            escaped_dir = root / "escaped"
            write_layer_run(escaped_dir, labels=labels)
            manifest_path = escaped_dir / "layers.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["layerMap"]["path"] = "../outside.npy"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(LayerRunError, "escapes"):
                load_layer_run(escaped_dir)

            invalid_dir = root / "invalid"
            write_layer_run(invalid_dir, labels=np.zeros((4, 3), dtype=np.uint8))
            with self.assertRaisesRegex(LayerRunError, "all labels"):
                load_layer_run(invalid_dir)


if __name__ == "__main__":
    unittest.main()
