"""Bounded horizontal camera planning for three-layer 2.5D scenes."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

BACKGROUND_LABEL = 0
MIDGROUND_LABEL = 1
FOREGROUND_LABEL = 2
LAYER_COUNT = 3


class VisibilityContractError(ValueError):
    """Raised when camera planning inputs or configuration are unsupported."""


@dataclass(frozen=True)
class VisibilityConfig:
    """Configuration for a bounded, discrete horizontal camera path.

    The foreground shift is limited by both a source-width fraction and a hard
    pixel cap. Background remains fixed, foreground moves at full displacement,
    and ``midground_parallax_factor`` controls the intermediate screen shift.
    """

    max_foreground_shift_fraction: float = 0.02
    max_foreground_shift_pixels: int = 64
    midground_parallax_factor: float = 0.5


@dataclass(frozen=True)
class VisibilityPlan:
    """Per-layer completion masks and endpoint hole diagnostics.

    Disocclusion masks use their target layer's source-grid coordinates.
    View-hole masks use output viewport coordinates. All arrays are boolean HxW
    maps with a top-left origin, x right, and y down.
    """

    max_foreground_shift_pixels: int
    layer_parallax_factors: tuple[float, float, float]
    sampled_positions: int
    background_disocclusion: np.ndarray
    midground_disocclusion: np.ndarray
    all_view_holes: np.ndarray
    left_view_holes: np.ndarray
    right_view_holes: np.ndarray


def _validate_config(config: VisibilityConfig) -> None:
    if (
        not math.isfinite(config.max_foreground_shift_fraction)
        or config.max_foreground_shift_fraction <= 0.0
        or config.max_foreground_shift_fraction > 0.1
    ):
        raise VisibilityContractError(
            "max_foreground_shift_fraction must be finite, positive, and at most 0.1"
        )
    if (
        isinstance(config.max_foreground_shift_pixels, bool)
        or config.max_foreground_shift_pixels < 1
        or config.max_foreground_shift_pixels > 512
    ):
        raise VisibilityContractError("max_foreground_shift_pixels must be between 1 and 512")
    if (
        not math.isfinite(config.midground_parallax_factor)
        or config.midground_parallax_factor <= 0.0
        or config.midground_parallax_factor >= 1.0
    ):
        raise VisibilityContractError(
            "midground_parallax_factor must be finite and between 0 and 1"
        )


def _validate_labels(labels: np.ndarray) -> np.ndarray:
    array = np.asarray(labels)
    if array.ndim != 2 or array.size == 0:
        raise VisibilityContractError("Layer labels must be a non-empty 2D array")
    if array.dtype != np.uint8:
        raise VisibilityContractError(f"Layer labels must be uint8, got {array.dtype}")
    if array.shape[1] < 2:
        raise VisibilityContractError("Horizontal camera planning requires width >= 2")
    if set(int(value) for value in np.unique(array)) != {0, 1, 2}:
        raise VisibilityContractError("Layer labels must contain all labels 0, 1, and 2 only")
    return np.ascontiguousarray(array)


def _round_half_away_from_zero(value: float) -> int:
    magnitude = math.floor(abs(value) + 0.5)
    return magnitude if value >= 0.0 else -magnitude


def translate_mask(mask: np.ndarray, horizontal_shift: int) -> np.ndarray:
    """Translate a boolean HxW mask horizontally with clipping and no wrapping."""

    array = np.asarray(mask)
    if array.ndim != 2 or array.dtype != np.bool_:
        raise VisibilityContractError("Translated masks must be 2D boolean arrays")
    if not isinstance(horizontal_shift, int) or isinstance(horizontal_shift, bool):
        raise VisibilityContractError("horizontal_shift must be an integer")
    width = array.shape[1]
    translated = np.zeros_like(array)
    if horizontal_shift >= width or horizontal_shift <= -width:
        return translated
    if horizontal_shift > 0:
        translated[:, horizontal_shift:] = array[:, : width - horizontal_shift]
    elif horizontal_shift < 0:
        translated[:, : width + horizontal_shift] = array[:, -horizontal_shift:]
    else:
        translated[:] = array
    return translated


def layer_screen_shifts(
    foreground_shift_pixels: int,
    *,
    midground_parallax_factor: float,
) -> tuple[int, int, int]:
    """Return background, midground, and foreground screen shifts in pixels."""

    if not isinstance(foreground_shift_pixels, int) or isinstance(foreground_shift_pixels, bool):
        raise VisibilityContractError("foreground_shift_pixels must be an integer")
    if (
        not math.isfinite(midground_parallax_factor)
        or midground_parallax_factor <= 0.0
        or midground_parallax_factor >= 1.0
    ):
        raise VisibilityContractError(
            "midground_parallax_factor must be finite and between 0 and 1"
        )

    return (
        0,
        _round_half_away_from_zero(foreground_shift_pixels * midground_parallax_factor),
        foreground_shift_pixels,
    )


def view_holes(labels: np.ndarray, shifts: tuple[int, int, int]) -> np.ndarray:
    """Return output pixels not covered by the shifted observed layer masks."""

    validated = _validate_labels(labels)
    if len(shifts) != LAYER_COUNT:
        raise VisibilityContractError("Exactly three layer shifts are required")
    coverage = np.zeros(validated.shape, dtype=np.bool_)
    for label, shift in enumerate(shifts):
        coverage |= translate_mask(validated == label, shift)
    return np.ascontiguousarray(~coverage)


def plan_visibility(
    labels: np.ndarray,
    *,
    config: VisibilityConfig | None = None,
) -> VisibilityPlan:
    """Plan every hidden target-layer pixel required by the bounded camera path.

    Camera position ``-1`` is the left endpoint, ``0`` is the source viewpoint,
    and ``+1`` is the right endpoint. A positive foreground screen shift
    corresponds to the left camera endpoint. Every integer foreground shift in
    the supported range is evaluated, so the masks cover all discrete viewer
    positions governed by this contract.
    """

    settings = config or VisibilityConfig()
    _validate_config(settings)
    validated = _validate_labels(labels)
    width = validated.shape[1]
    fractional_limit = max(
        1,
        _round_half_away_from_zero(width * settings.max_foreground_shift_fraction),
    )
    max_shift = min(
        width - 1,
        settings.max_foreground_shift_pixels,
        fractional_limit,
    )

    layer_masks = tuple(validated == label for label in range(LAYER_COUNT))
    background_occluded = validated > BACKGROUND_LABEL
    midground_occluded = validated > MIDGROUND_LABEL
    background_disocclusion = np.zeros(validated.shape, dtype=np.bool_)
    midground_disocclusion = np.zeros(validated.shape, dtype=np.bool_)

    for foreground_shift in range(-max_shift, max_shift + 1):
        shifts = layer_screen_shifts(
            foreground_shift,
            midground_parallax_factor=settings.midground_parallax_factor,
        )
        background_coverage = translate_mask(layer_masks[MIDGROUND_LABEL], shifts[1])
        background_coverage |= translate_mask(layer_masks[FOREGROUND_LABEL], shifts[2])
        background_disocclusion |= background_occluded & ~background_coverage

        foreground_relative_to_midground = shifts[2] - shifts[1]
        midground_coverage = translate_mask(
            layer_masks[FOREGROUND_LABEL],
            foreground_relative_to_midground,
        )
        midground_disocclusion |= midground_occluded & ~midground_coverage

    left_shifts = layer_screen_shifts(
        max_shift,
        midground_parallax_factor=settings.midground_parallax_factor,
    )
    right_shifts = layer_screen_shifts(
        -max_shift,
        midground_parallax_factor=settings.midground_parallax_factor,
    )
    left_holes = view_holes(validated, left_shifts)
    right_holes = view_holes(validated, right_shifts)

    return VisibilityPlan(
        max_foreground_shift_pixels=max_shift,
        layer_parallax_factors=(
            0.0,
            settings.midground_parallax_factor,
            1.0,
        ),
        sampled_positions=max_shift * 2 + 1,
        background_disocclusion=np.ascontiguousarray(background_disocclusion),
        midground_disocclusion=np.ascontiguousarray(midground_disocclusion),
        all_view_holes=np.ascontiguousarray(background_disocclusion.copy()),
        left_view_holes=left_holes,
        right_view_holes=right_holes,
    )


def disocclusion_preview(plan: VisibilityPlan) -> np.ndarray:
    """Render target-layer completion requirements with a fixed RGB palette."""

    if plan.background_disocclusion.shape != plan.midground_disocclusion.shape:
        raise VisibilityContractError("Disocclusion masks must share one shape")
    state = plan.background_disocclusion.astype(np.uint8)
    state += plan.midground_disocclusion.astype(np.uint8) * 2
    palette = np.array(
        [
            [0, 0, 0],
            [65, 105, 225],
            [242, 186, 73],
            [190, 74, 130],
        ],
        dtype=np.uint8,
    )
    return palette[state]
