"""Bounded camera evaluation for the continuous relative-depth mesh."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
from PIL import Image

from .mesh_renderer import MeshRenderResult, render_orthographic_mesh
from .mesh_run import LoadedMeshRun


class MeshVisibilityError(ValueError):
    """Raised when a mesh camera plan cannot satisfy its contract."""


@dataclass(frozen=True)
class MeshVisibilityConfig:
    """Resource and motion limits for the provisional mesh-camera baseline."""

    max_render_dimension: int = 512
    max_faces: int = 500_000
    max_near_shift_fraction: float = 0.02
    max_near_shift_pixels: int = 64
    sampled_positions: int = 3
    hole_color: tuple[int, int, int] = (0, 0, 0)


@dataclass(frozen=True)
class MeshVisibilityPlan:
    """Rendered endpoints and missing-pixel masks for a bounded camera path.

    ``sampled_coverages`` and ``sampled_depths`` remain in viewport coordinates
    and align one-to-one with ``camera_positions``. They are retained in memory
    so later stages can distinguish depth-consistent disocclusions from generic
    black viewport pixels without rendering the mesh a second time.
    """

    center_view: np.ndarray
    left_view: np.ndarray
    right_view: np.ndarray
    center_geometry_holes: np.ndarray
    left_view_holes: np.ndarray
    right_view_holes: np.ndarray
    all_view_holes: np.ndarray
    render_width: int
    render_height: int
    max_near_shift_pixels: int
    camera_positions: tuple[float, ...]
    render_seconds: tuple[float, ...]
    sampled_coverages: tuple[np.ndarray, ...]
    sampled_depths: tuple[np.ndarray, ...]
    default_view_pixel_identical: bool


def _validate_config(config: MeshVisibilityConfig) -> None:
    if (
        isinstance(config.max_render_dimension, bool)
        or config.max_render_dimension < 2
        or config.max_render_dimension > 2048
    ):
        raise MeshVisibilityError("max_render_dimension must be between 2 and 2048")
    if isinstance(config.max_faces, bool) or config.max_faces < 1 or config.max_faces > 2_000_000:
        raise MeshVisibilityError("max_faces must be between 1 and 2000000")
    if (
        not math.isfinite(config.max_near_shift_fraction)
        or config.max_near_shift_fraction <= 0.0
        or config.max_near_shift_fraction > 0.1
    ):
        raise MeshVisibilityError("max_near_shift_fraction must be finite and in (0, 0.1]")
    if (
        isinstance(config.max_near_shift_pixels, bool)
        or config.max_near_shift_pixels < 1
        or config.max_near_shift_pixels > 256
    ):
        raise MeshVisibilityError("max_near_shift_pixels must be between 1 and 256")
    if (
        isinstance(config.sampled_positions, bool)
        or config.sampled_positions < 3
        or config.sampled_positions > 33
        or config.sampled_positions % 2 == 0
    ):
        raise MeshVisibilityError("sampled_positions must be an odd integer between 3 and 33")
    if len(config.hole_color) != 3 or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 255
        for value in config.hole_color
    ):
        raise MeshVisibilityError("hole_color must contain three integers in [0, 255]")


def _render_dimensions(width: int, height: int, *, maximum: int) -> tuple[int, int]:
    longest = max(width, height)
    if longest <= maximum:
        return width, height
    scale = maximum / longest
    return max(2, int(round(width * scale))), max(2, int(round(height * scale)))


def _observed_reference(texture: np.ndarray, *, width: int, height: int) -> np.ndarray:
    if texture.shape[:2] == (height, width):
        return np.ascontiguousarray(texture.copy())
    image = Image.fromarray(texture, mode="RGB")
    resized = image.resize((width, height), resample=Image.Resampling.LANCZOS)
    return np.ascontiguousarray(np.asarray(resized).copy(), dtype=np.uint8)


def plan_mesh_visibility(
    mesh: LoadedMeshRun,
    *,
    config: MeshVisibilityConfig | None = None,
) -> MeshVisibilityPlan:
    """Render a small camera path and identify uncovered viewport pixels.

    Position ``-1`` is the left camera endpoint and moves near content right;
    ``+1`` is the right endpoint and moves it left. The default view uses the
    observed texture directly so the source composition remains unchanged.
    Mesh-only coverage at that same view is disclosed separately.
    """

    settings = config or MeshVisibilityConfig()
    _validate_config(settings)
    if mesh.faces.shape[0] > settings.max_faces:
        raise MeshVisibilityError(
            f"Mesh has {mesh.faces.shape[0]} faces, exceeding max_faces={settings.max_faces}"
        )
    render_width, render_height = _render_dimensions(
        mesh.width,
        mesh.height,
        maximum=settings.max_render_dimension,
    )
    max_near_shift_pixels = min(
        max(1, int(round(render_width * settings.max_near_shift_fraction))),
        settings.max_near_shift_pixels,
    )
    camera_positions = tuple(
        float(value)
        for value in np.linspace(-1.0, 1.0, settings.sampled_positions, dtype=np.float32)
    )
    rendered: list[MeshRenderResult] = []
    render_seconds: list[float] = []
    for position in camera_positions:
        started = time.perf_counter()
        view = render_orthographic_mesh(
            mesh.texture,
            mesh.vertices,
            mesh.texture_coordinates,
            mesh.faces,
            width=render_width,
            height=render_height,
            camera_position=position,
            max_near_shift_pixels=max_near_shift_pixels,
            hole_color=settings.hole_color,
        )
        render_seconds.append(time.perf_counter() - started)
        rendered.append(view)

    center_index = settings.sampled_positions // 2
    center_geometry_holes = ~rendered[center_index].coverage
    left_view_holes = ~rendered[0].coverage
    right_view_holes = ~rendered[-1].coverage
    non_default_holes = [
        ~view.coverage for index, view in enumerate(rendered) if index != center_index
    ]
    all_view_holes = np.logical_or.reduce(non_default_holes)
    center_view = _observed_reference(
        mesh.texture,
        width=render_width,
        height=render_height,
    )
    expected_default = _observed_reference(
        mesh.texture,
        width=render_width,
        height=render_height,
    )
    return MeshVisibilityPlan(
        center_view=center_view,
        left_view=np.ascontiguousarray(rendered[0].color),
        right_view=np.ascontiguousarray(rendered[-1].color),
        center_geometry_holes=np.ascontiguousarray(center_geometry_holes),
        left_view_holes=np.ascontiguousarray(left_view_holes),
        right_view_holes=np.ascontiguousarray(right_view_holes),
        all_view_holes=np.ascontiguousarray(all_view_holes),
        render_width=render_width,
        render_height=render_height,
        max_near_shift_pixels=max_near_shift_pixels,
        camera_positions=camera_positions,
        render_seconds=tuple(render_seconds),
        sampled_coverages=tuple(view.coverage for view in rendered),
        sampled_depths=tuple(view.depth for view in rendered),
        default_view_pixel_identical=bool(np.array_equal(center_view, expected_default)),
    )
