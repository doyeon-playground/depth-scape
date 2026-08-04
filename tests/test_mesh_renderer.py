from __future__ import annotations

import unittest

import numpy as np
from PIL import Image

from depth_scape.mesh import MeshBuildConfig, build_continuous_depth_mesh
from depth_scape.mesh_renderer import MeshRenderError, render_orthographic_mesh


def _textured_grid(width: int = 5, height: int = 4, *, depth_value: float = 0.0):
    y, x = np.mgrid[:height, :width]
    texture = np.stack((x * 30, y * 40, (x + y) * 15), axis=-1).astype(np.uint8)
    depth = np.full((height, width), depth_value, dtype=np.float32)
    mesh = build_continuous_depth_mesh(
        Image.fromarray(texture, mode="RGB"),
        depth,
        config=MeshBuildConfig(max_mesh_dimension=max(width, height), depth_jump_threshold=1.0),
    )
    return texture, mesh


class MeshRendererTests(unittest.TestCase):
    def test_default_view_reproduces_an_uncut_full_resolution_grid(self) -> None:
        texture, mesh = _textured_grid()

        result = render_orthographic_mesh(
            texture,
            mesh.vertices,
            mesh.texture_coordinates,
            mesh.faces,
            width=5,
            height=4,
            camera_position=0.0,
            max_near_shift_pixels=1,
        )

        self.assertTrue(result.coverage.all())
        np.testing.assert_array_equal(result.color, texture)
        self.assertEqual(result.depth.dtype, np.float32)

    def test_near_plane_moves_opposite_camera_and_exposes_a_border(self) -> None:
        texture, mesh = _textured_grid(depth_value=1.0)

        left_camera = render_orthographic_mesh(
            texture,
            mesh.vertices,
            mesh.texture_coordinates,
            mesh.faces,
            width=5,
            height=4,
            camera_position=-1.0,
            max_near_shift_pixels=1,
        )
        right_camera = render_orthographic_mesh(
            texture,
            mesh.vertices,
            mesh.texture_coordinates,
            mesh.faces,
            width=5,
            height=4,
            camera_position=1.0,
            max_near_shift_pixels=1,
        )

        self.assertFalse(left_camera.coverage[:, 0].any())
        self.assertFalse(right_camera.coverage[:, -1].any())
        self.assertTrue(left_camera.coverage[:, 1:].all())
        self.assertTrue(right_camera.coverage[:, :-1].all())

    def test_larger_relative_depth_wins_for_overlapping_faces(self) -> None:
        texture = np.array(
            [
                [[220, 20, 20], [20, 220, 20]],
                [[220, 20, 20], [20, 220, 20]],
            ],
            dtype=np.uint8,
        )
        positions = np.array([[-1, 1], [1, 1], [-1, -1]], dtype=np.float32)
        far = np.column_stack((positions, np.full(3, 0.1, dtype=np.float32)))
        near = np.column_stack((positions, np.full(3, 0.9, dtype=np.float32)))
        vertices = np.ascontiguousarray(np.concatenate((near, far)), dtype=np.float32)
        uv = np.ascontiguousarray(
            np.concatenate(
                (
                    np.tile(np.array([[1.0, 0.0]], dtype=np.float32), (3, 1)),
                    np.tile(np.array([[0.0, 0.0]], dtype=np.float32), (3, 1)),
                )
            )
        )
        faces = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.int32)

        result = render_orthographic_mesh(
            texture,
            vertices,
            uv,
            faces,
            width=3,
            height=3,
            camera_position=0.0,
            max_near_shift_pixels=0,
        )

        np.testing.assert_array_equal(result.color[0, 0], np.array([20, 220, 20]))
        self.assertAlmostEqual(float(result.depth[0, 0]), 0.9, places=6)

    def test_rejects_invalid_camera_and_array_contracts(self) -> None:
        texture, mesh = _textured_grid()
        with self.assertRaises(MeshRenderError):
            render_orthographic_mesh(
                texture,
                mesh.vertices,
                mesh.texture_coordinates,
                mesh.faces,
                width=5,
                height=4,
                camera_position=1.1,
                max_near_shift_pixels=1,
            )
        with self.assertRaises(MeshRenderError):
            render_orthographic_mesh(
                texture,
                mesh.vertices.astype(np.float64),
                mesh.texture_coordinates,
                mesh.faces,
                width=5,
                height=4,
                camera_position=0.0,
                max_near_shift_pixels=1,
            )


if __name__ == "__main__":
    unittest.main()
