from __future__ import annotations

import unittest

import numpy as np

from depth_scape.depth import (
    DepthContractError,
    depth_preview,
    normalize_relative_depth,
)


class NormalizeRelativeDepthTests(unittest.TestCase):
    def test_normalizes_float_depth_and_preserves_order(self) -> None:
        raw = np.array([[2.0, 4.0], [6.0, 10.0]], dtype=np.float64)

        normalized, raw_min, raw_max = normalize_relative_depth(
            raw,
            expected_height=2,
            expected_width=2,
        )

        self.assertEqual(normalized.dtype, np.float32)
        self.assertEqual(normalized.shape, (2, 2))
        self.assertEqual(raw_min, 2.0)
        self.assertEqual(raw_max, 10.0)
        self.assertEqual(float(normalized[0, 0]), 0.0)
        self.assertEqual(float(normalized[1, 1]), 1.0)
        self.assertGreater(float(normalized[1, 0]), float(normalized[0, 1]))

    def test_rejects_wrong_shape_nonfinite_integer_and_flat_outputs(self) -> None:
        invalid_cases = (
            np.ones((1, 2, 2), dtype=np.float32),
            np.array([[0.0, np.nan], [1.0, 2.0]], dtype=np.float32),
            np.array([[0, 1], [2, 3]], dtype=np.int32),
            np.ones((2, 2), dtype=np.float32),
        )
        for values in invalid_cases:
            with (
                self.subTest(shape=values.shape, dtype=values.dtype),
                self.assertRaises(DepthContractError),
            ):
                normalize_relative_depth(
                    values,
                    expected_height=2,
                    expected_width=2,
                )

    def test_preview_maps_far_to_black_and_near_to_white(self) -> None:
        depth = np.array([[0.0, 0.5, 1.0]], dtype=np.float32)
        preview = depth_preview(depth)
        np.testing.assert_array_equal(preview, np.array([[0, 128, 255]], dtype=np.uint8))


if __name__ == "__main__":
    unittest.main()
