from __future__ import annotations

import unittest

import numpy as np

from depth_scape.visibility import (
    VisibilityConfig,
    VisibilityContractError,
    disocclusion_preview,
    layer_screen_shifts,
    plan_visibility,
    translate_mask,
    view_holes,
)


def _layer_labels() -> np.ndarray:
    labels = np.zeros((6, 20), dtype=np.uint8)
    labels[:, 5:15] = 1
    labels[:, 8:12] = 2
    return labels


class VisibilityPlanTests(unittest.TestCase):
    def test_plans_all_discrete_positions_and_preserves_default_view(self) -> None:
        labels = _layer_labels()
        config = VisibilityConfig(
            max_foreground_shift_fraction=0.1,
            max_foreground_shift_pixels=4,
            midground_parallax_factor=0.5,
        )

        plan = plan_visibility(labels, config=config)

        self.assertEqual(plan.max_foreground_shift_pixels, 2)
        self.assertEqual(plan.sampled_positions, 5)
        self.assertEqual(plan.layer_parallax_factors, (0.0, 0.5, 1.0))
        self.assertTrue(plan.background_disocclusion.any())
        self.assertTrue(plan.midground_disocclusion.any())
        self.assertFalse(view_holes(labels, (0, 0, 0)).any())
        np.testing.assert_array_equal(
            plan.all_view_holes,
            plan.background_disocclusion,
        )
        self.assertTrue(np.all(~plan.background_disocclusion | (labels > 0)))
        self.assertTrue(np.all(~plan.midground_disocclusion | (labels > 1)))

        background_texture = (labels == 0) | plan.background_disocclusion
        midground_texture = (labels == 1) | plan.midground_disocclusion
        foreground_texture = labels == 2
        for foreground_shift in range(-2, 3):
            shifts = layer_screen_shifts(
                foreground_shift,
                midground_parallax_factor=0.5,
            )
            coverage = translate_mask(background_texture, shifts[0])
            coverage |= translate_mask(midground_texture, shifts[1])
            coverage |= translate_mask(foreground_texture, shifts[2])
            self.assertTrue(coverage.all())

        left_shifts = layer_screen_shifts(2, midground_parallax_factor=0.5)
        right_shifts = layer_screen_shifts(-2, midground_parallax_factor=0.5)
        np.testing.assert_array_equal(plan.left_view_holes, view_holes(labels, left_shifts))
        np.testing.assert_array_equal(
            plan.right_view_holes,
            view_holes(labels, right_shifts),
        )

    def test_translation_clips_without_wrapping(self) -> None:
        mask = np.array([[True, False, False, True]], dtype=np.bool_)

        np.testing.assert_array_equal(
            translate_mask(mask, 1),
            np.array([[False, True, False, False]], dtype=np.bool_),
        )
        np.testing.assert_array_equal(
            translate_mask(mask, -1),
            np.array([[False, False, True, False]], dtype=np.bool_),
        )
        self.assertFalse(translate_mask(mask, 4).any())

    def test_rejects_invalid_configuration_labels_and_shifts(self) -> None:
        labels = _layer_labels()
        invalid_configs = (
            VisibilityConfig(max_foreground_shift_fraction=0.0),
            VisibilityConfig(max_foreground_shift_fraction=0.11),
            VisibilityConfig(max_foreground_shift_pixels=0),
            VisibilityConfig(midground_parallax_factor=0.0),
            VisibilityConfig(midground_parallax_factor=1.0),
        )
        for config in invalid_configs:
            with self.subTest(config=config), self.assertRaises(VisibilityContractError):
                plan_visibility(labels, config=config)

        invalid_labels = (
            labels.astype(np.int32),
            labels[:, :1],
            np.zeros_like(labels),
            labels[None, :, :],
        )
        for invalid in invalid_labels:
            with self.subTest(shape=invalid.shape), self.assertRaises(VisibilityContractError):
                plan_visibility(invalid)

        with self.assertRaises(VisibilityContractError):
            translate_mask(labels == 0, 1.5)  # type: ignore[arg-type]

    def test_preview_distinguishes_target_layers_and_overlap(self) -> None:
        plan = plan_visibility(
            _layer_labels(),
            config=VisibilityConfig(max_foreground_shift_fraction=0.1),
        )

        preview = disocclusion_preview(plan)

        self.assertEqual(preview.dtype, np.uint8)
        self.assertEqual(preview.shape, (6, 20, 3))
        self.assertGreaterEqual(np.unique(preview.reshape(-1, 3), axis=0).shape[0], 3)


if __name__ == "__main__":
    unittest.main()
