"""Validation and normalization for relative-depth artifacts."""

from __future__ import annotations

import numpy as np


class DepthContractError(ValueError):
    """Raised when model output cannot satisfy the depth artifact contract."""


def normalize_relative_depth(
    values: np.ndarray,
    *,
    expected_height: int,
    expected_width: int,
) -> tuple[np.ndarray, float, float]:
    """Return an aligned float32 proximity map normalized to ``[0, 1]``.

    The input and result use row-major ``(height, width)`` coordinates with
    ``(0, 0)`` at the top left. Larger values mean nearer content. The result is
    unitless and must never be interpreted as metric distance.
    """

    array = np.asarray(values)
    expected_shape = (expected_height, expected_width)
    if array.shape != expected_shape:
        raise DepthContractError(
            f"Depth shape {array.shape} does not match normalized image {expected_shape}"
        )
    if not np.issubdtype(array.dtype, np.floating):
        raise DepthContractError(f"Depth dtype must be floating point, got {array.dtype}")
    if not np.isfinite(array).all():
        raise DepthContractError("Depth output contains NaN or infinite values")

    raw_min = float(array.min())
    raw_max = float(array.max())
    dynamic_range = raw_max - raw_min
    if dynamic_range <= np.finfo(np.float32).eps:
        raise DepthContractError("Depth output has no usable dynamic range")

    normalized = (array.astype(np.float32, copy=False) - raw_min) / dynamic_range
    normalized = np.clip(normalized, 0.0, 1.0).astype(np.float32, copy=False)
    return np.ascontiguousarray(normalized), raw_min, raw_max


def depth_preview(depth: np.ndarray) -> np.ndarray:
    """Convert normalized proximity to an 8-bit grayscale preview.

    White is near and black is far. The preview is for inspection only; numeric
    consumers must use the float32 artifact.
    """

    if depth.ndim != 2 or depth.dtype != np.float32:
        raise DepthContractError("Preview input must be a 2D float32 array")
    if not np.isfinite(depth).all() or depth.min() < 0.0 or depth.max() > 1.0:
        raise DepthContractError("Preview input must contain finite values in [0, 1]")
    return np.rint(depth * 255.0).astype(np.uint8)
