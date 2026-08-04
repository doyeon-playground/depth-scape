from __future__ import annotations

import unittest

import numpy as np
from PIL import Image

from depth_scape.mesh import (
    MeshBuildConfig,
    MeshContractError,
    build_continuous_depth_mesh,
    mesh_preview,
)


def _image(height: int = 4, width: int = 5) -> Image.Image:
    y, x = np.mgrid[:height, :width]
    values = np.stack((x * 20, y * 30, (x + y) * 10), axis=-1).astype(np.uint8)
    return Image.fromarray(values, mode="RGB")


class ContinuousDepthMeshTests(unittest.TestCase):
    def test_builds_aspect_correct_mesh_with_complete_uncut_grid(self) -> None:
        image = _image()
        depth = np.zeros((4, 5), dtype=np.float32)

        result = build_continuous_depth_mesh(
            image,
            depth,
            config=MeshBuildConfig(max_mesh_dimension=5, depth_jump_threshold=1.0),
        )

        self.assertEqual(result.vertices.shape, (20, 3))
        self.assertEqual(result.vertices.dtype, np.float32)
        self.assertEqual(result.texture_coordinates.shape, (20, 2))
        self.assertEqual(result.texture_coordinates.dtype, np.float32)
        self.assertEqual(result.faces.shape, (24, 3))
        self.assertEqual(result.faces.dtype, np.int32)
        self.assertEqual(result.sampling_stride, 1)
        self.assertFalse(result.cut_cells.any())
        self.assertFalse(result.cut_source_mask.any())
        self.assertEqual(result.retained_face_fraction, 1.0)
        np.testing.assert_allclose(result.vertices[0], (-1.25, 1.0, 0.0))
        np.testing.assert_allclose(result.vertices[-1], (1.25, -1.0, 0.0))
        np.testing.assert_allclose(result.texture_coordinates[0], (0.0, 0.0))
        np.testing.assert_allclose(result.texture_coordinates[-1], (1.0, 1.0))
        first_triangle = result.vertices[result.faces[0]]
        normal = np.cross(
            first_triangle[1] - first_triangle[0],
            first_triangle[2] - first_triangle[0],
        )
        self.assertGreater(float(normal[2]), 0.0)

    def test_cuts_faces_crossing_a_depth_cliff_without_semantic_labels(self) -> None:
        image = _image(height=5, width=6)
        depth = np.full((5, 6), 0.1, dtype=np.float32)
        depth[:, 3:] = 0.8

        result = build_continuous_depth_mesh(
            image,
            depth,
            config=MeshBuildConfig(max_mesh_dimension=6, depth_jump_threshold=0.2),
        )

        self.assertTrue(result.cut_cells.any())
        self.assertTrue(result.cut_source_mask[:, 2:4].all())
        self.assertGreater(result.faces.shape[0], 0)
        face_depth = result.vertices[result.faces, 2]
        self.assertTrue(np.all(np.ptp(face_depth, axis=1) <= 0.2))
        self.assertLess(result.retained_face_fraction, 1.0)

    def test_preview_preserves_rgb_outside_red_cut_overlay(self) -> None:
        image = _image()
        mask = np.zeros((4, 5), dtype=np.bool_)
        mask[1:3, 2] = True

        preview = mesh_preview(image, mask, overlay_alpha=0.5)
        source = np.asarray(image)

        np.testing.assert_array_equal(preview[~mask], source[~mask])
        self.assertTrue(np.any(preview[mask] != source[mask]))
        self.assertEqual(preview.shape, (4, 5, 3))
        self.assertEqual(preview.dtype, np.uint8)

    def test_rejects_invalid_configuration_and_misaligned_depth(self) -> None:
        image = _image()
        depth = np.zeros((4, 5), dtype=np.float32)
        invalid_configs = (
            MeshBuildConfig(max_mesh_dimension=1),
            MeshBuildConfig(max_mesh_dimension=2049),
            MeshBuildConfig(depth_jump_threshold=0.0),
            MeshBuildConfig(depth_jump_threshold=1.1),
            MeshBuildConfig(preview_overlay_alpha=0.0),
        )
        for config in invalid_configs:
            with self.subTest(config=config), self.assertRaises(MeshContractError):
                build_continuous_depth_mesh(image, depth, config=config)

        with self.assertRaisesRegex(MeshContractError, "does not match"):
            build_continuous_depth_mesh(image, depth[:, :-1])
        with self.assertRaisesRegex(MeshContractError, "float32"):
            build_continuous_depth_mesh(image, depth.astype(np.float64))
        invalid_range = depth.copy()
        invalid_range[0, 0] = np.nan
        with self.assertRaisesRegex(MeshContractError, "finite"):
            build_continuous_depth_mesh(image, invalid_range)


if __name__ == "__main__":
    unittest.main()
