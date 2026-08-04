"""Deterministic CPU rendering for image-textured relative-depth meshes."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


class MeshRenderError(ValueError):
    """Raised when mesh rendering inputs violate their numeric contract."""


@dataclass(frozen=True)
class MeshRenderResult:
    """One orthographic mesh view.

    ``color`` is uint8 ``HxWx3``. ``coverage`` is boolean ``HxW`` and marks
    pixels backed by observed texture through retained mesh faces. ``depth`` is
    float32 ``HxW`` relative proximity with ``-inf`` for uncovered pixels.
    """

    color: np.ndarray
    coverage: np.ndarray
    depth: np.ndarray


def _validate_inputs(
    texture: np.ndarray,
    vertices: np.ndarray,
    texture_coordinates: np.ndarray,
    faces: np.ndarray,
    *,
    width: int,
    height: int,
    camera_position: float,
    max_near_shift_pixels: int,
) -> None:
    if texture.dtype != np.uint8 or texture.ndim != 3 or texture.shape[2] != 3:
        raise MeshRenderError("texture must be a uint8 HxWx3 array")
    if vertices.dtype != np.float32 or vertices.ndim != 2 or vertices.shape[1] != 3:
        raise MeshRenderError("vertices must be a float32 Nx3 array")
    if texture_coordinates.dtype != np.float32 or texture_coordinates.shape != (
        vertices.shape[0],
        2,
    ):
        raise MeshRenderError("texture_coordinates must be float32 Nx2 aligned to vertices")
    if faces.dtype != np.int32 or faces.ndim != 2 or faces.shape[1] != 3:
        raise MeshRenderError("faces must be an int32 Mx3 array")
    if faces.size == 0 or faces.min() < 0 or faces.max() >= vertices.shape[0]:
        raise MeshRenderError("faces must contain valid vertex indices")
    if not np.isfinite(vertices).all() or not np.isfinite(texture_coordinates).all():
        raise MeshRenderError("vertices and texture_coordinates must be finite")
    if texture_coordinates.min() < 0.0 or texture_coordinates.max() > 1.0:
        raise MeshRenderError("texture_coordinates must be in [0, 1]")
    if isinstance(width, bool) or isinstance(height, bool) or width < 2 or height < 2:
        raise MeshRenderError("render width and height must be integers >= 2")
    if not math.isfinite(camera_position) or camera_position < -1.0 or camera_position > 1.0:
        raise MeshRenderError("camera_position must be finite and in [-1, 1]")
    if isinstance(max_near_shift_pixels, bool) or max_near_shift_pixels < 0:
        raise MeshRenderError("max_near_shift_pixels must be a non-negative integer")


def _project_vertices(
    vertices: np.ndarray,
    *,
    source_aspect_ratio: float,
    width: int,
    height: int,
    camera_position: float,
    max_near_shift_pixels: int,
) -> np.ndarray:
    u = vertices[:, 0] / np.float32(2.0 * source_aspect_ratio) + np.float32(0.5)
    v = np.float32(0.5) - vertices[:, 1] / np.float32(2.0)
    x = u * np.float32(width - 1)
    x -= np.float32(camera_position) * np.float32(max_near_shift_pixels) * vertices[:, 2]
    y = v * np.float32(height - 1)
    return np.ascontiguousarray(np.column_stack((x, y)), dtype=np.float32)


def render_orthographic_mesh(
    texture: np.ndarray,
    vertices: np.ndarray,
    texture_coordinates: np.ndarray,
    faces: np.ndarray,
    *,
    width: int,
    height: int,
    camera_position: float,
    max_near_shift_pixels: int,
    hole_color: tuple[int, int, int] = (0, 0, 0),
) -> MeshRenderResult:
    """Render one bounded horizontal view with a larger-relative-Z-wins buffer.

    The camera is orthographic. At position ``-1`` nearer vertices move right;
    at ``+1`` they move left. Texture lookup is nearest-neighbor so an uncut,
    full-resolution grid reproduces observed pixels exactly at position zero.
    """

    _validate_inputs(
        texture,
        vertices,
        texture_coordinates,
        faces,
        width=width,
        height=height,
        camera_position=camera_position,
        max_near_shift_pixels=max_near_shift_pixels,
    )
    if len(hole_color) != 3 or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 255
        for value in hole_color
    ):
        raise MeshRenderError("hole_color must contain three integers in [0, 255]")

    source_height, source_width = texture.shape[:2]
    projected = _project_vertices(
        vertices,
        source_aspect_ratio=source_width / source_height,
        width=width,
        height=height,
        camera_position=camera_position,
        max_near_shift_pixels=max_near_shift_pixels,
    )
    color = np.empty((height, width, 3), dtype=np.uint8)
    color[:] = hole_color
    depth_buffer = np.full((height, width), -np.inf, dtype=np.float32)
    epsilon = np.float32(1e-5)
    texture_width_scale = np.float32(source_width - 1)
    texture_height_scale = np.float32(source_height - 1)

    for face in faces:
        indices = face.astype(np.intp, copy=False)
        triangle = projected[indices]
        x0, y0 = triangle[0]
        x1, y1 = triangle[1]
        x2, y2 = triangle[2]
        minimum_x = max(0, int(math.floor(float(min(x0, x1, x2)))))
        maximum_x = min(width - 1, int(math.ceil(float(max(x0, x1, x2)))))
        minimum_y = max(0, int(math.floor(float(min(y0, y1, y2)))))
        maximum_y = min(height - 1, int(math.ceil(float(max(y0, y1, y2)))))
        if minimum_x > maximum_x or minimum_y > maximum_y:
            continue

        denominator = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(float(denominator)) <= 1e-12:
            continue
        pixel_y, pixel_x = np.mgrid[
            minimum_y : maximum_y + 1,
            minimum_x : maximum_x + 1,
        ]
        pixel_x = pixel_x.astype(np.float32, copy=False)
        pixel_y = pixel_y.astype(np.float32, copy=False)
        weight_0 = ((y1 - y2) * (pixel_x - x2) + (x2 - x1) * (pixel_y - y2)) / denominator
        weight_1 = ((y2 - y0) * (pixel_x - x2) + (x0 - x2) * (pixel_y - y2)) / denominator
        weight_2 = np.float32(1.0) - weight_0 - weight_1
        inside = (weight_0 >= -epsilon) & (weight_1 >= -epsilon) & (weight_2 >= -epsilon)
        if not inside.any():
            continue

        triangle_depth = vertices[indices, 2]
        interpolated_depth = (
            weight_0 * triangle_depth[0]
            + weight_1 * triangle_depth[1]
            + weight_2 * triangle_depth[2]
        )
        target_depth = depth_buffer[
            minimum_y : maximum_y + 1,
            minimum_x : maximum_x + 1,
        ]
        update = inside & (interpolated_depth > target_depth)
        if not update.any():
            continue

        triangle_uv = texture_coordinates[indices]
        interpolated_u = (
            weight_0 * triangle_uv[0, 0]
            + weight_1 * triangle_uv[1, 0]
            + weight_2 * triangle_uv[2, 0]
        )
        interpolated_v = (
            weight_0 * triangle_uv[0, 1]
            + weight_1 * triangle_uv[1, 1]
            + weight_2 * triangle_uv[2, 1]
        )
        texture_x = np.rint(interpolated_u * texture_width_scale).astype(np.intp)
        texture_y = np.rint(interpolated_v * texture_height_scale).astype(np.intp)
        np.clip(texture_x, 0, source_width - 1, out=texture_x)
        np.clip(texture_y, 0, source_height - 1, out=texture_y)

        target_color = color[
            minimum_y : maximum_y + 1,
            minimum_x : maximum_x + 1,
        ]
        target_depth[update] = interpolated_depth[update]
        target_color[update] = texture[texture_y[update], texture_x[update]]

    coverage = np.isfinite(depth_buffer)
    return MeshRenderResult(
        color=np.ascontiguousarray(color),
        coverage=np.ascontiguousarray(coverage),
        depth=np.ascontiguousarray(depth_buffer),
    )
