from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from depth_scape.mesh import MeshBuildConfig, build_continuous_depth_mesh
from depth_scape.mesh_run import LoadedMeshRun
from depth_scape.mesh_visibility import (
    MeshVisibilityConfig,
    MeshVisibilityError,
    plan_mesh_visibility,
)


def _loaded_mesh(*, cut: bool = False) -> LoadedMeshRun:
    height, width = 6, 10
    y, x = np.mgrid[:height, :width]
    texture = np.stack((x * 20, y * 30, (x + y) * 10), axis=-1).astype(np.uint8)
    depth = np.ones((height, width), dtype=np.float32)
    if cut:
        depth[:, :5] = 0.1
    result = build_continuous_depth_mesh(
        Image.fromarray(texture, mode="RGB"),
        depth,
        config=MeshBuildConfig(max_mesh_dimension=10, depth_jump_threshold=0.2),
    )
    return LoadedMeshRun(
        texture=texture,
        vertices=result.vertices,
        texture_coordinates=result.texture_coordinates,
        faces=result.faces,
        source_sha256="a" * 64,
        manifest_sha256="b" * 64,
        manifest_path=Path("mesh.json"),
        algorithm_id="continuous-depth-grid-cut",
        algorithm_version="0.1",
    )


class MeshVisibilityTests(unittest.TestCase):
    def test_preserves_default_view_and_unions_bounded_endpoint_holes(self) -> None:
        mesh = _loaded_mesh()
        plan = plan_mesh_visibility(
            mesh,
            config=MeshVisibilityConfig(
                max_render_dimension=10,
                max_near_shift_fraction=0.1,
                max_near_shift_pixels=2,
                sampled_positions=3,
            ),
        )

        np.testing.assert_array_equal(plan.center_view, mesh.texture)
        self.assertTrue(plan.default_view_pixel_identical)
        self.assertFalse(plan.center_geometry_holes.any())
        self.assertTrue(plan.left_view_holes[:, 0].all())
        self.assertTrue(plan.right_view_holes[:, -1].all())
        np.testing.assert_array_equal(
            plan.all_view_holes,
            plan.left_view_holes | plan.right_view_holes,
        )
        self.assertEqual(plan.camera_positions, (-1.0, 0.0, 1.0))
        self.assertEqual(plan.max_near_shift_pixels, 1)

    def test_refined_cut_preserves_simple_center_coverage_and_reveals_motion_holes(self) -> None:
        mesh = _loaded_mesh(cut=True)

        plan = plan_mesh_visibility(
            mesh,
            config=MeshVisibilityConfig(max_render_dimension=10),
        )

        np.testing.assert_array_equal(plan.center_view, mesh.texture)
        self.assertFalse(plan.center_geometry_holes.any())
        self.assertTrue(plan.all_view_holes.any())

    def test_bounds_render_size_and_rejects_invalid_configuration(self) -> None:
        plan = plan_mesh_visibility(
            _loaded_mesh(),
            config=MeshVisibilityConfig(max_render_dimension=5),
        )
        self.assertEqual((plan.render_width, plan.render_height), (5, 3))
        self.assertEqual(plan.center_view.shape, (3, 5, 3))

        invalid = (
            MeshVisibilityConfig(max_render_dimension=1),
            MeshVisibilityConfig(max_faces=0),
            MeshVisibilityConfig(max_faces=2_000_001),
            MeshVisibilityConfig(max_near_shift_fraction=0.0),
            MeshVisibilityConfig(max_near_shift_fraction=0.11),
            MeshVisibilityConfig(max_near_shift_pixels=0),
            MeshVisibilityConfig(sampled_positions=4),
            MeshVisibilityConfig(sampled_positions=35),
        )
        for config in invalid:
            with self.subTest(config=config), self.assertRaises(MeshVisibilityError):
                plan_mesh_visibility(_loaded_mesh(), config=config)


if __name__ == "__main__":
    unittest.main()
