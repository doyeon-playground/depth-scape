"""Continuous relative-depth mesh construction with depth-edge cuts."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image


class MeshContractError(ValueError):
    """Raised when continuous-mesh inputs or outputs violate their contract."""


@dataclass(frozen=True)
class MeshBuildConfig:
    """Configuration for the provisional continuous-depth mesh baseline."""

    max_mesh_dimension: int = 384
    depth_jump_threshold: float = 0.02
    refine_depth_boundaries: bool = True
    max_refined_source_cells: int = 2_000_000
    preview_overlay_alpha: float = 0.65


@dataclass(frozen=True)
class MeshBuildResult:
    """Aspect-correct mesh arrays and depth-discontinuity diagnostics.

    ``vertices`` is float32 ``Nx3``. X points right, Y points up, and Z is the
    unitless relative-proximity value from the aligned depth map, so larger Z
    values are nearer. ``texture_coordinates`` is float32 ``Nx2`` with a
    top-left origin, U right, and V down. ``faces`` is int32 ``Mx3`` with
    counter-clockwise winding when viewed from positive Z.
    """

    vertices: np.ndarray
    texture_coordinates: np.ndarray
    faces: np.ndarray
    sample_x: np.ndarray
    sample_y: np.ndarray
    cut_cells: np.ndarray
    cut_source_mask: np.ndarray
    sampling_stride: int
    retained_face_fraction: float
    refined_base_cell_count: int
    refined_source_cell_count: int
    residual_cut_source_cell_count: int


def _validate_config(config: MeshBuildConfig) -> None:
    if (
        isinstance(config.max_mesh_dimension, bool)
        or config.max_mesh_dimension < 2
        or config.max_mesh_dimension > 2048
    ):
        raise MeshContractError("max_mesh_dimension must be between 2 and 2048")
    if (
        not math.isfinite(config.depth_jump_threshold)
        or config.depth_jump_threshold <= 0.0
        or config.depth_jump_threshold > 1.0
    ):
        raise MeshContractError("depth_jump_threshold must be finite and in (0, 1]")
    if not isinstance(config.refine_depth_boundaries, bool):
        raise MeshContractError("refine_depth_boundaries must be a boolean")
    if (
        isinstance(config.max_refined_source_cells, bool)
        or config.max_refined_source_cells < 1
        or config.max_refined_source_cells > 20_000_000
    ):
        raise MeshContractError("max_refined_source_cells must be between 1 and 20000000")
    if (
        not math.isfinite(config.preview_overlay_alpha)
        or config.preview_overlay_alpha <= 0.0
        or config.preview_overlay_alpha > 1.0
    ):
        raise MeshContractError("preview_overlay_alpha must be finite and in (0, 1]")


def _validate_inputs(image: Image.Image, depth: np.ndarray) -> np.ndarray:
    if image.mode != "RGB":
        raise MeshContractError(f"Expected an RGB image, got {image.mode}")
    if image.width < 2 or image.height < 2:
        raise MeshContractError("Continuous mesh construction requires width and height >= 2")
    array = np.asarray(depth)
    if array.shape != (image.height, image.width):
        raise MeshContractError(
            f"Depth shape {array.shape} does not match image {(image.height, image.width)}"
        )
    if array.dtype != np.float32:
        raise MeshContractError(f"Depth dtype must be float32, got {array.dtype}")
    if not np.isfinite(array).all() or array.min() < 0.0 or array.max() > 1.0:
        raise MeshContractError("Depth must contain finite values in [0, 1]")
    return np.ascontiguousarray(array)


def _sample_axis(size: int, *, stride: int) -> np.ndarray:
    samples = np.arange(0, size, stride, dtype=np.int32)
    if samples[-1] != size - 1:
        samples = np.append(samples, np.int32(size - 1))
    return np.ascontiguousarray(samples, dtype=np.int32)


def _jump_pixels(depth: np.ndarray, *, threshold: float) -> np.ndarray:
    """Mark both endpoints of every four-connected depth discontinuity."""

    jumps = np.zeros(depth.shape, dtype=np.bool_)
    horizontal = np.abs(depth[:, 1:] - depth[:, :-1]) > threshold
    vertical = np.abs(depth[1:, :] - depth[:-1, :]) > threshold
    jumps[:, :-1] |= horizontal
    jumps[:, 1:] |= horizontal
    jumps[:-1, :] |= vertical
    jumps[1:, :] |= vertical
    return jumps


def _cut_cells_from_jumps(
    jumps: np.ndarray,
    *,
    sample_x: np.ndarray,
    sample_y: np.ndarray,
) -> np.ndarray:
    """Return grid cells containing at least one source-grid discontinuity."""

    integral = np.pad(jumps.astype(np.int32), ((1, 0), (1, 0)))
    integral = integral.cumsum(axis=0, dtype=np.int32).cumsum(axis=1, dtype=np.int32)
    top = sample_y[:-1, None]
    bottom = sample_y[1:, None] + 1
    left = sample_x[None, :-1]
    right = sample_x[None, 1:] + 1
    counts = (
        integral[bottom, right]
        - integral[top, right]
        - integral[bottom, left]
        + integral[top, left]
    )
    return np.ascontiguousarray(counts > 0)


def _add_cut_cells_to_differences(
    cut_cells: np.ndarray,
    *,
    sample_x: np.ndarray,
    sample_y: np.ndarray,
    differences: np.ndarray,
) -> None:
    if not cut_cells.any():
        return

    cell_y, cell_x = np.nonzero(cut_cells)
    top = sample_y[cell_y]
    bottom = sample_y[cell_y + 1] + 1
    left = sample_x[cell_x]
    right = sample_x[cell_x + 1] + 1
    np.add.at(differences, (top, left), 1)
    np.add.at(differences, (bottom, left), -1)
    np.add.at(differences, (top, right), -1)
    np.add.at(differences, (bottom, right), 1)


def _source_mask_from_differences(
    differences: np.ndarray,
    *,
    height: int,
    width: int,
) -> np.ndarray:
    coverage = differences.cumsum(axis=0, dtype=np.int32).cumsum(axis=1, dtype=np.int32)
    return np.ascontiguousarray(coverage[:height, :width] > 0)


def _build_faces(cut_cells: np.ndarray) -> np.ndarray:
    grid_height = cut_cells.shape[0] + 1
    grid_width = cut_cells.shape[1] + 1
    indices = np.arange(grid_height * grid_width, dtype=np.int32).reshape(grid_height, grid_width)
    valid = ~cut_cells
    top_left = indices[:-1, :-1][valid]
    top_right = indices[:-1, 1:][valid]
    bottom_left = indices[1:, :-1][valid]
    bottom_right = indices[1:, 1:][valid]
    first = np.column_stack((top_left, bottom_left, bottom_right))
    second = np.column_stack((top_left, bottom_right, top_right))
    faces = np.concatenate((first, second), axis=0).astype(np.int32, copy=False)
    return np.ascontiguousarray(faces)


def _mesh_arrays(
    depth: np.ndarray,
    *,
    sample_x: np.ndarray,
    sample_y: np.ndarray,
    width: int,
    height: int,
) -> tuple[np.ndarray, np.ndarray]:
    u = sample_x.astype(np.float32) / np.float32(width - 1)
    v = sample_y.astype(np.float32) / np.float32(height - 1)
    u_grid, v_grid = np.meshgrid(u, v)
    sampled_depth = depth[np.ix_(sample_y, sample_x)]
    aspect_ratio = np.float32(width / height)
    x_grid = (u_grid - np.float32(0.5)) * np.float32(2.0) * aspect_ratio
    y_grid = (np.float32(0.5) - v_grid) * np.float32(2.0)
    vertices = np.column_stack((x_grid.ravel(), y_grid.ravel(), sampled_depth.ravel())).astype(
        np.float32, copy=False
    )
    texture_coordinates = np.column_stack((u_grid.ravel(), v_grid.ravel())).astype(
        np.float32, copy=False
    )
    return np.ascontiguousarray(vertices), np.ascontiguousarray(texture_coordinates)


def _corner_depth_cut_cells(sampled_depth: np.ndarray, *, threshold: float) -> np.ndarray:
    top_left = sampled_depth[:-1, :-1]
    top_right = sampled_depth[:-1, 1:]
    bottom_left = sampled_depth[1:, :-1]
    bottom_right = sampled_depth[1:, 1:]
    minimum = np.minimum(np.minimum(top_left, top_right), np.minimum(bottom_left, bottom_right))
    maximum = np.maximum(np.maximum(top_left, top_right), np.maximum(bottom_left, bottom_right))
    return np.ascontiguousarray(maximum - minimum > threshold)


def _refined_source_cell_count(
    cut_cells: np.ndarray,
    *,
    sample_x: np.ndarray,
    sample_y: np.ndarray,
) -> int:
    cell_y, cell_x = np.nonzero(cut_cells)
    widths = sample_x[cell_x + 1].astype(np.int64) - sample_x[cell_x].astype(np.int64)
    heights = sample_y[cell_y + 1].astype(np.int64) - sample_y[cell_y].astype(np.int64)
    return int(np.sum(widths * heights, dtype=np.int64))


def build_continuous_depth_mesh(
    image: Image.Image,
    depth: np.ndarray,
    *,
    config: MeshBuildConfig | None = None,
) -> MeshBuildResult:
    """Build an aspect-correct mesh and cut cells that cross sharp depth jumps.

    The algorithm is category-independent: it does not identify sky, terrain,
    buildings, or other semantic classes. Source RGB is not modified here.
    """

    settings = config or MeshBuildConfig()
    _validate_config(settings)
    validated_depth = _validate_inputs(image, depth)
    longest_span = max(image.width - 1, image.height - 1)
    sampling_stride = max(
        1,
        math.ceil(longest_span / (settings.max_mesh_dimension - 1)),
    )
    sample_x = _sample_axis(image.width, stride=sampling_stride)
    sample_y = _sample_axis(image.height, stride=sampling_stride)

    vertices, texture_coordinates = _mesh_arrays(
        validated_depth,
        sample_x=sample_x,
        sample_y=sample_y,
        width=image.width,
        height=image.height,
    )

    jumps = _jump_pixels(validated_depth, threshold=settings.depth_jump_threshold)
    cut_cells = _cut_cells_from_jumps(
        jumps,
        sample_x=sample_x,
        sample_y=sample_y,
    )
    base_faces = _build_faces(cut_cells)
    vertex_blocks = [vertices]
    texture_coordinate_blocks = [texture_coordinates]
    face_blocks = [base_faces]
    cut_differences = np.zeros((image.height + 1, image.width + 1), dtype=np.int32)
    refined_base_cell_count = 0
    refined_source_cell_count = 0
    residual_cut_source_cell_count = int(np.count_nonzero(cut_cells))
    candidate_cell_count = int(cut_cells.size)

    if settings.refine_depth_boundaries and cut_cells.any():
        refined_base_cell_count = int(np.count_nonzero(cut_cells))
        refined_source_cell_count = _refined_source_cell_count(
            cut_cells,
            sample_x=sample_x,
            sample_y=sample_y,
        )
        if refined_source_cell_count > settings.max_refined_source_cells:
            raise MeshContractError(
                "Depth-boundary refinement requires "
                f"{refined_source_cell_count} source cells, exceeding "
                f"max_refined_source_cells={settings.max_refined_source_cells}"
            )
        candidate_cell_count = int(np.count_nonzero(~cut_cells)) + refined_source_cell_count
        residual_cut_source_cell_count = 0
        vertex_offset = int(vertices.shape[0])
        for cell_y, cell_x in zip(*np.nonzero(cut_cells), strict=True):
            local_x = np.arange(
                int(sample_x[cell_x]),
                int(sample_x[cell_x + 1]) + 1,
                dtype=np.int32,
            )
            local_y = np.arange(
                int(sample_y[cell_y]),
                int(sample_y[cell_y + 1]) + 1,
                dtype=np.int32,
            )
            local_depth = validated_depth[np.ix_(local_y, local_x)]
            local_cut_cells = _corner_depth_cut_cells(
                local_depth,
                threshold=settings.depth_jump_threshold,
            )
            residual_cut_source_cell_count += int(np.count_nonzero(local_cut_cells))
            _add_cut_cells_to_differences(
                local_cut_cells,
                sample_x=local_x,
                sample_y=local_y,
                differences=cut_differences,
            )
            local_faces = _build_faces(local_cut_cells)
            if local_faces.size == 0:
                continue
            local_vertices, local_texture_coordinates = _mesh_arrays(
                validated_depth,
                sample_x=local_x,
                sample_y=local_y,
                width=image.width,
                height=image.height,
            )
            vertex_blocks.append(local_vertices)
            texture_coordinate_blocks.append(local_texture_coordinates)
            face_blocks.append(local_faces + np.int32(vertex_offset))
            vertex_offset += int(local_vertices.shape[0])
    else:
        _add_cut_cells_to_differences(
            cut_cells,
            sample_x=sample_x,
            sample_y=sample_y,
            differences=cut_differences,
        )

    vertices = np.ascontiguousarray(np.concatenate(vertex_blocks, axis=0), dtype=np.float32)
    texture_coordinates = np.ascontiguousarray(
        np.concatenate(texture_coordinate_blocks, axis=0),
        dtype=np.float32,
    )
    faces = np.ascontiguousarray(np.concatenate(face_blocks, axis=0), dtype=np.int32)
    if faces.size == 0:
        raise MeshContractError(
            "Depth discontinuities removed every mesh cell; increase depth_jump_threshold"
        )
    cut_source_mask = _source_mask_from_differences(
        cut_differences,
        height=image.height,
        width=image.width,
    )
    retained_face_fraction = float(faces.shape[0] / (2 * candidate_cell_count))
    return MeshBuildResult(
        vertices=np.ascontiguousarray(vertices),
        texture_coordinates=np.ascontiguousarray(texture_coordinates),
        faces=faces,
        sample_x=sample_x,
        sample_y=sample_y,
        cut_cells=cut_cells,
        cut_source_mask=cut_source_mask,
        sampling_stride=sampling_stride,
        retained_face_fraction=retained_face_fraction,
        refined_base_cell_count=refined_base_cell_count,
        refined_source_cell_count=refined_source_cell_count,
        residual_cut_source_cell_count=residual_cut_source_cell_count,
    )


def mesh_preview(
    image: Image.Image,
    cut_source_mask: np.ndarray,
    *,
    overlay_alpha: float,
) -> np.ndarray:
    """Overlay cut regions on observed RGB without hiding unaffected content."""

    if image.mode != "RGB":
        raise MeshContractError(f"Expected an RGB image, got {image.mode}")
    mask = np.asarray(cut_source_mask)
    if mask.shape != (image.height, image.width) or mask.dtype != np.bool_:
        raise MeshContractError("cut_source_mask must be a boolean image-aligned array")
    if not math.isfinite(overlay_alpha) or overlay_alpha <= 0.0 or overlay_alpha > 1.0:
        raise MeshContractError("overlay_alpha must be finite and in (0, 1]")

    source = np.asarray(image, dtype=np.uint8)
    preview = source.copy()
    overlay = np.array([255.0, 64.0, 64.0], dtype=np.float32)
    blended = np.rint(
        source[mask].astype(np.float32) * (1.0 - overlay_alpha) + overlay * overlay_alpha
    ).astype(np.uint8)
    preview[mask] = blended
    return np.ascontiguousarray(preview)
