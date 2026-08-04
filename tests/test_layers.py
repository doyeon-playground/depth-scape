from __future__ import annotations

import unittest

import numpy as np
from PIL import Image

from depth_scape.layers import (
    LAYER_PALETTE,
    LayerBuildConfig,
    LayerContractError,
    build_layers,
    layer_preview,
    refine_depth_with_edges,
)


class LayerBuildTests(unittest.TestCase):
    def test_builds_exhaustive_far_to_near_layers(self) -> None:
        image = Image.new("RGB", (12, 9), (100, 120, 140))
        depth = np.vstack(
            (
                np.full((3, 12), 0.1, dtype=np.float32),
                np.full((3, 12), 0.5, dtype=np.float32),
                np.full((3, 12), 0.9, dtype=np.float32),
            )
        )

        result = build_layers(image, depth)

        self.assertEqual(result.labels.dtype, np.uint8)
        self.assertEqual(result.labels.shape, depth.shape)
        np.testing.assert_array_equal(result.labels[1], np.zeros(12, dtype=np.uint8))
        np.testing.assert_array_equal(result.labels[4], np.ones(12, dtype=np.uint8))
        np.testing.assert_array_equal(result.labels[7], np.full(12, 2, dtype=np.uint8))
        self.assertLess(result.centers[0], result.centers[1])
        self.assertLess(result.centers[1], result.centers[2])
        self.assertAlmostEqual(sum(result.fractions), 1.0)
        self.assertEqual(set(np.unique(result.labels)), {0, 1, 2})

    def test_edge_strength_preserves_a_depth_discontinuity_during_smoothing(self) -> None:
        depth = np.array(
            [
                [0.1, 0.1, 0.9, 0.9],
                [0.1, 0.1, 0.9, 0.9],
                [0.1, 0.1, 0.9, 0.9],
            ],
            dtype=np.float32,
        )
        edge = np.zeros_like(depth)
        edge[:, 1:3] = 1.0

        refined = refine_depth_with_edges(depth, edge, iterations=3)

        np.testing.assert_array_equal(refined[:, 1:3], depth[:, 1:3])
        self.assertTrue(np.isfinite(refined).all())
        self.assertGreaterEqual(float(refined.min()), 0.0)
        self.assertLessEqual(float(refined.max()), 1.0)

    def test_rejects_invalid_depth_and_degenerate_layer_distribution(self) -> None:
        image = Image.new("RGB", (4, 3))
        invalid_depths = (
            np.zeros((3, 4), dtype=np.float64),
            np.zeros((4, 3), dtype=np.float32),
            np.full((3, 4), np.nan, dtype=np.float32),
            np.ones((3, 4), dtype=np.float32),
        )
        for depth in invalid_depths:
            with (
                self.subTest(shape=depth.shape, dtype=depth.dtype),
                self.assertRaises(LayerContractError),
            ):
                build_layers(image, depth)

        depth = np.linspace(0.0, 1.0, 12, dtype=np.float32).reshape(3, 4)
        with self.assertRaisesRegex(LayerContractError, "min_layer_fraction"):
            build_layers(image, depth, config=LayerBuildConfig(min_layer_fraction=0.34))

    def test_preview_uses_the_fixed_diagnostic_palette(self) -> None:
        labels = np.array([[0, 1, 2]], dtype=np.uint8)

        preview = layer_preview(labels)

        np.testing.assert_array_equal(preview[0], LAYER_PALETTE)
        with self.assertRaises(LayerContractError):
            layer_preview(labels.astype(np.int32))


if __name__ == "__main__":
    unittest.main()
