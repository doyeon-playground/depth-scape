"""Canonical hidden-surface requests derived from bounded mesh views."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .mesh_visibility import MeshVisibilityPlan

REQUIRED_GENERATED_CHANNELS = ("rgb", "relative_depth")


class HiddenSurfaceContractError(ValueError):
    """Raised when hidden-surface planning inputs violate their contract."""


@dataclass(frozen=True)
class HiddenSurfaceConfig:
    """Limits for mapping viewport holes to a canonical hidden surface."""

    min_depth_separation: float = 0.02
    max_request_pixels: int = 2_000_000


@dataclass(frozen=True)
class HiddenSurfacePlan:
    """Coupled RGB-and-depth generation request on a canonical render grid.

    ``request_mask`` is a boolean ``HxW`` mask in the default-view render grid.
    It addresses a separate hidden surface and never replaces observed RGB.
    Every included pixel requires both generated RGB and generated relative
    depth. ``relative_depth_hint`` is an inferred far-side support value and
    ``max_relative_depth_exclusive`` keeps generated content behind every
    associated occluder. Both float32 arrays contain NaN outside the mask.

    ``outpaint_request_mask`` is boolean ``Hx(W+2P)`` where ``P`` is
    ``horizontal_padding``. The observed default view occupies columns
    ``[P, P+W)`` and is always excluded from this mask. Requested pixels extend
    the nearest visible edge surface without using semantic classes.

    The per-view masks use viewport coordinates. ``mapped_view_holes`` records
    interior holes represented by the canonical hidden-surface request, while
    ``outpaint_mapped_view_holes`` records holes represented by horizontal
    overscan. Remaining holes lack a safe mapping. None contains generated
    content yet.
    """

    request_mask: np.ndarray
    relative_depth_hint: np.ndarray
    max_relative_depth_exclusive: np.ndarray
    request_observation_count: np.ndarray
    outpaint_request_mask: np.ndarray
    outpaint_relative_depth_hint: np.ndarray
    outpaint_request_observation_count: np.ndarray
    horizontal_padding: int
    mapped_view_holes: tuple[np.ndarray, ...]
    outpaint_mapped_view_holes: tuple[np.ndarray, ...]
    border_view_holes: tuple[np.ndarray, ...]
    unmapped_border_view_holes: tuple[np.ndarray, ...]
    ambiguous_depth_view_holes: tuple[np.ndarray, ...]
    unresolved_view_holes: tuple[np.ndarray, ...]
    all_mapped_view_holes: np.ndarray
    all_outpaint_mapped_view_holes: np.ndarray
    all_supported_view_holes: np.ndarray
    all_border_view_holes: np.ndarray
    all_unmapped_border_view_holes: np.ndarray
    all_ambiguous_depth_view_holes: np.ndarray
    all_unresolved_view_holes: np.ndarray
    camera_positions: tuple[float, ...]
    required_generated_channels: tuple[str, str]


def validate_hidden_surface_config(config: HiddenSurfaceConfig) -> None:
    """Reject hidden-surface settings before expensive mesh rendering begins."""

    if (
        not math.isfinite(config.min_depth_separation)
        or config.min_depth_separation <= 0.0
        or config.min_depth_separation > 1.0
    ):
        raise HiddenSurfaceContractError("min_depth_separation must be finite and in (0, 1]")
    if (
        isinstance(config.max_request_pixels, bool)
        or config.max_request_pixels < 1
        or config.max_request_pixels > 20_000_000
    ):
        raise HiddenSurfaceContractError("max_request_pixels must be between 1 and 20000000")


def _validate_visibility(plan: MeshVisibilityPlan) -> None:
    shape = (plan.render_height, plan.render_width)
    if plan.render_width < 2 or plan.render_height < 2:
        raise HiddenSurfaceContractError("render dimensions must both be at least 2")
    if isinstance(plan.max_near_shift_pixels, bool) or plan.max_near_shift_pixels < 1:
        raise HiddenSurfaceContractError("max_near_shift_pixels must be a positive integer")
    count = len(plan.camera_positions)
    if count < 3 or count % 2 == 0:
        raise HiddenSurfaceContractError("camera_positions must contain an odd count >= 3")
    if len(plan.sampled_coverages) != count or len(plan.sampled_depths) != count:
        raise HiddenSurfaceContractError(
            "sampled coverage and depth arrays must align with camera_positions"
        )
    if not all(
        math.isfinite(position) and -1.0 <= position <= 1.0 for position in plan.camera_positions
    ):
        raise HiddenSurfaceContractError("camera positions must be finite and in [-1, 1]")
    center_index = count // 2
    if not math.isclose(plan.camera_positions[center_index], 0.0, abs_tol=1e-7):
        raise HiddenSurfaceContractError("the center camera position must be 0")
    if any(
        current >= following
        for current, following in zip(
            plan.camera_positions,
            plan.camera_positions[1:],
        )
    ):
        raise HiddenSurfaceContractError("camera positions must be strictly increasing")

    for index, (coverage, depth) in enumerate(
        zip(plan.sampled_coverages, plan.sampled_depths, strict=True)
    ):
        if coverage.shape != shape or coverage.dtype != np.bool_:
            raise HiddenSurfaceContractError(
                f"sampled coverage {index} must be a boolean {shape} array"
            )
        if depth.shape != shape or depth.dtype != np.float32:
            raise HiddenSurfaceContractError(
                f"sampled depth {index} must be a float32 {shape} array"
            )
        if not np.array_equal(np.isfinite(depth), coverage):
            raise HiddenSurfaceContractError(
                f"sampled depth {index} must be finite exactly where coverage is true"
            )
        if coverage.any() and (depth[coverage].min() < 0.0 or depth[coverage].max() > 1.0):
            raise HiddenSurfaceContractError(
                f"sampled depth {index} covered values must be in [0, 1]"
            )


def _rounded_pixel(values: np.ndarray) -> np.ndarray:
    """Round float coordinates to the nearest integer, with halves away from zero."""

    rounded = np.where(values >= 0.0, np.floor(values + 0.5), np.ceil(values - 0.5))
    return rounded.astype(np.int32)


def _hole_runs(row: np.ndarray) -> tuple[tuple[int, int], ...]:
    indices = np.flatnonzero(row)
    if indices.size == 0:
        return ()
    breaks = np.flatnonzero(np.diff(indices) > 1) + 1
    groups = np.split(indices, breaks)
    return tuple((int(group[0]), int(group[-1]) + 1) for group in groups)


def plan_hidden_surfaces(
    visibility: MeshVisibilityPlan,
    *,
    config: HiddenSurfaceConfig | None = None,
) -> HiddenSurfacePlan:
    """Map depth-consistent viewport holes into one hidden-surface request.

    For positive camera positions, near content moves left, so a supported hole
    must be bounded by nearer depth on its left and farther depth on its right.
    The relation is reversed for negative positions. A far-side depth hint is
    used to invert the horizontal projection into the canonical default-view
    grid. Frame holes are mapped to a padded horizontal canvas using the nearest
    visible edge depth as a continuation hint. Inconsistent boundaries remain
    unresolved rather than being presented as recoverable scene content.
    """

    settings = config or HiddenSurfaceConfig()
    validate_hidden_surface_config(settings)
    _validate_visibility(visibility)

    height = visibility.render_height
    width = visibility.render_width
    horizontal_padding = visibility.max_near_shift_pixels
    outpaint_width = width + horizontal_padding * 2
    request_depth_hint = np.full((height, width), np.inf, dtype=np.float32)
    request_depth_ceiling = np.full((height, width), np.inf, dtype=np.float32)
    request_observation_count = np.zeros((height, width), dtype=np.uint16)
    outpaint_depth_sum = np.zeros((height, outpaint_width), dtype=np.float32)
    outpaint_observation_count = np.zeros((height, outpaint_width), dtype=np.uint16)
    mapped_masks: list[np.ndarray] = []
    outpaint_mapped_masks: list[np.ndarray] = []
    border_masks: list[np.ndarray] = []
    unmapped_border_masks: list[np.ndarray] = []
    ambiguous_masks: list[np.ndarray] = []
    unresolved_masks: list[np.ndarray] = []
    center_index = len(visibility.camera_positions) // 2

    for view_index, (position, coverage, depth) in enumerate(
        zip(
            visibility.camera_positions,
            visibility.sampled_coverages,
            visibility.sampled_depths,
            strict=True,
        )
    ):
        holes = ~coverage
        mapped = np.zeros((height, width), dtype=np.bool_)
        outpaint_mapped = np.zeros((height, width), dtype=np.bool_)
        border = np.zeros((height, width), dtype=np.bool_)
        ambiguous = np.zeros((height, width), dtype=np.bool_)
        if view_index == center_index:
            mapped_masks.append(mapped)
            outpaint_mapped_masks.append(outpaint_mapped)
            border_masks.append(border)
            unmapped_border_masks.append(border.copy())
            ambiguous_masks.append(ambiguous)
            unresolved_masks.append(mapped.copy())
            continue

        for y in range(height):
            for start, stop in _hole_runs(holes[y]):
                if start == 0 or stop == width:
                    border[y, start:stop] = True
                    if start == 0 and stop == width:
                        continue
                    support_depth = float(depth[y, stop] if start == 0 else depth[y, start - 1])
                    view_x_int = np.arange(start, stop, dtype=np.int32)
                    canonical_float = view_x_int.astype(np.float32) + np.float32(
                        position
                    ) * np.float32(horizontal_padding) * np.float32(support_depth)
                    if start == 0:
                        canonical_x = np.floor(canonical_float).astype(np.int32)
                        outpaint_valid = (canonical_float < 0.0) & (
                            canonical_x >= -horizontal_padding
                        )
                    else:
                        canonical_x = np.ceil(canonical_float).astype(np.int32)
                        outpaint_valid = (canonical_float > np.float32(width - 1)) & (
                            canonical_x < width + horizontal_padding
                        )
                    if outpaint_valid.any():
                        valid_view_x = view_x_int[outpaint_valid]
                        atlas_x = canonical_x[outpaint_valid] + horizontal_padding
                        outpaint_mapped[y, valid_view_x] = True
                        np.add.at(
                            outpaint_depth_sum[y],
                            atlas_x,
                            np.float32(support_depth),
                        )
                        np.add.at(
                            outpaint_observation_count[y],
                            atlas_x,
                            np.uint16(1),
                        )
                    continue
                left_depth = float(depth[y, start - 1])
                right_depth = float(depth[y, stop])
                if position > 0.0:
                    near_depth = left_depth
                    far_depth = right_depth
                else:
                    near_depth = right_depth
                    far_depth = left_depth
                if near_depth - far_depth < settings.min_depth_separation:
                    ambiguous[y, start:stop] = True
                    continue

                view_x = np.arange(start, stop, dtype=np.float32)
                canonical_x = _rounded_pixel(
                    view_x
                    + np.float32(position)
                    * np.float32(visibility.max_near_shift_pixels)
                    * np.float32(far_depth)
                )
                valid = (canonical_x >= 0) & (canonical_x < width)
                view_x_int = np.arange(start, stop, dtype=np.int32)
                if valid.any():
                    valid_view_x = view_x_int[valid]
                    valid_canonical_x = canonical_x[valid]
                    mapped[y, valid_view_x] = True
                    np.minimum.at(
                        request_depth_hint[y],
                        valid_canonical_x,
                        np.float32(far_depth),
                    )
                    np.minimum.at(
                        request_depth_ceiling[y],
                        valid_canonical_x,
                        np.float32(near_depth),
                    )
                    np.add.at(
                        request_observation_count[y],
                        valid_canonical_x,
                        np.uint16(1),
                    )

                outpaint_valid = (
                    (canonical_x >= -horizontal_padding)
                    & (canonical_x < width + horizontal_padding)
                    & ~valid
                )
                if outpaint_valid.any():
                    valid_view_x = view_x_int[outpaint_valid]
                    atlas_x = canonical_x[outpaint_valid] + horizontal_padding
                    border[y, valid_view_x] = True
                    outpaint_mapped[y, valid_view_x] = True
                    np.add.at(
                        outpaint_depth_sum[y],
                        atlas_x,
                        np.float32(far_depth),
                    )
                    np.add.at(
                        outpaint_observation_count[y],
                        atlas_x,
                        np.uint16(1),
                    )

        mapped_masks.append(np.ascontiguousarray(mapped))
        outpaint_mapped_masks.append(np.ascontiguousarray(outpaint_mapped))
        border_masks.append(np.ascontiguousarray(border))
        unmapped_border_masks.append(np.ascontiguousarray(border & ~outpaint_mapped))
        ambiguous_masks.append(np.ascontiguousarray(ambiguous))
        unresolved_masks.append(np.ascontiguousarray(holes & ~(mapped | outpaint_mapped)))

    request_mask = request_observation_count > 0
    outpaint_request_mask = outpaint_observation_count > 0
    source_start = horizontal_padding
    source_stop = source_start + width
    if outpaint_request_mask[:, source_start:source_stop].any():
        raise HiddenSurfaceContractError("outpaint request must not replace observed pixels")
    outpaint_depth_hint = np.full((height, outpaint_width), np.nan, dtype=np.float32)
    outpaint_depth_hint[outpaint_request_mask] = outpaint_depth_sum[
        outpaint_request_mask
    ] / outpaint_observation_count[outpaint_request_mask].astype(np.float32)
    request_pixels = int(np.count_nonzero(request_mask) + np.count_nonzero(outpaint_request_mask))
    if request_pixels > settings.max_request_pixels:
        raise HiddenSurfaceContractError(
            f"Combined hidden-surface request has {request_pixels} pixels, exceeding "
            f"max_request_pixels={settings.max_request_pixels}"
        )
    if request_mask.any() and not np.all(
        request_depth_hint[request_mask] < request_depth_ceiling[request_mask]
    ):
        raise HiddenSurfaceContractError(
            "inferred hidden depth hints must remain behind their occluders"
        )

    request_depth_hint[~request_mask] = np.nan
    request_depth_ceiling[~request_mask] = np.nan
    non_default_indices = [index for index in range(len(mapped_masks)) if index != center_index]
    all_mapped = np.logical_or.reduce([mapped_masks[index] for index in non_default_indices])
    all_outpaint_mapped = np.logical_or.reduce(
        [outpaint_mapped_masks[index] for index in non_default_indices]
    )
    all_supported = all_mapped | all_outpaint_mapped
    all_border = np.logical_or.reduce([border_masks[index] for index in non_default_indices])
    all_unmapped_border = np.logical_or.reduce(
        [unmapped_border_masks[index] for index in non_default_indices]
    )
    all_ambiguous = np.logical_or.reduce([ambiguous_masks[index] for index in non_default_indices])
    all_unresolved = np.logical_or.reduce(
        [unresolved_masks[index] for index in non_default_indices]
    )
    return HiddenSurfacePlan(
        request_mask=np.ascontiguousarray(request_mask),
        relative_depth_hint=np.ascontiguousarray(request_depth_hint),
        max_relative_depth_exclusive=np.ascontiguousarray(request_depth_ceiling),
        request_observation_count=np.ascontiguousarray(request_observation_count),
        outpaint_request_mask=np.ascontiguousarray(outpaint_request_mask),
        outpaint_relative_depth_hint=np.ascontiguousarray(outpaint_depth_hint),
        outpaint_request_observation_count=np.ascontiguousarray(outpaint_observation_count),
        horizontal_padding=horizontal_padding,
        mapped_view_holes=tuple(mapped_masks),
        outpaint_mapped_view_holes=tuple(outpaint_mapped_masks),
        border_view_holes=tuple(border_masks),
        unmapped_border_view_holes=tuple(unmapped_border_masks),
        ambiguous_depth_view_holes=tuple(ambiguous_masks),
        unresolved_view_holes=tuple(unresolved_masks),
        all_mapped_view_holes=np.ascontiguousarray(all_mapped),
        all_outpaint_mapped_view_holes=np.ascontiguousarray(all_outpaint_mapped),
        all_supported_view_holes=np.ascontiguousarray(all_supported),
        all_border_view_holes=np.ascontiguousarray(all_border),
        all_unmapped_border_view_holes=np.ascontiguousarray(all_unmapped_border),
        all_ambiguous_depth_view_holes=np.ascontiguousarray(all_ambiguous),
        all_unresolved_view_holes=np.ascontiguousarray(all_unresolved),
        camera_positions=visibility.camera_positions,
        required_generated_channels=REQUIRED_GENERATED_CHANNELS,
    )
