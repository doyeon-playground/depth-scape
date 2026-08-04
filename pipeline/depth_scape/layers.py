"""Deterministic foreground, midground, and background layer construction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

BACKGROUND_LABEL = 0
MIDGROUND_LABEL = 1
FOREGROUND_LABEL = 2
LAYER_NAMES = ("background", "midground", "foreground")
LAYER_PALETTE = np.array(
    [
        [65, 105, 225],
        [242, 186, 73],
        [190, 74, 130],
    ],
    dtype=np.uint8,
)


class LayerContractError(ValueError):
    """Raised when layer inputs or outputs violate the pixel-alignment contract."""


@dataclass(frozen=True)
class LayerBuildConfig:
    """Configuration for the provisional three-layer baseline."""

    histogram_bins: int = 4096
    max_kmeans_iterations: int = 64
    convergence_tolerance: float = 1e-6
    smoothing_iterations: int = 2
    edge_percentile: float = 90.0
    min_layer_fraction: float = 0.01


@dataclass(frozen=True)
class LayerBuildResult:
    """Pixel-aligned inferred layer artifacts ordered from far to near."""

    refined_depth: np.ndarray
    boundary_strength: np.ndarray
    labels: np.ndarray
    centers: tuple[float, float, float]
    thresholds: tuple[float, float]
    fractions: tuple[float, float, float]
    iterations: int


def _validate_config(config: LayerBuildConfig) -> None:
    if config.histogram_bins < 32 or config.histogram_bins > 65_536:
        raise LayerContractError("histogram_bins must be between 32 and 65536")
    if config.max_kmeans_iterations < 1 or config.max_kmeans_iterations > 1000:
        raise LayerContractError("max_kmeans_iterations must be between 1 and 1000")
    if config.convergence_tolerance <= 0.0:
        raise LayerContractError("convergence_tolerance must be positive")
    if config.smoothing_iterations < 0 or config.smoothing_iterations > 20:
        raise LayerContractError("smoothing_iterations must be between 0 and 20")
    if config.edge_percentile < 50.0 or config.edge_percentile > 100.0:
        raise LayerContractError("edge_percentile must be between 50 and 100")
    if config.min_layer_fraction <= 0.0 or config.min_layer_fraction >= 1.0 / 3.0:
        raise LayerContractError("min_layer_fraction must be greater than 0 and below 1/3")


def _validate_inputs(image: Image.Image, depth: np.ndarray) -> np.ndarray:
    if image.mode != "RGB":
        raise LayerContractError(f"Expected an RGB image, got {image.mode}")
    array = np.asarray(depth)
    if array.shape != (image.height, image.width):
        raise LayerContractError(
            f"Depth shape {array.shape} does not match image {(image.height, image.width)}"
        )
    if array.dtype != np.float32:
        raise LayerContractError(f"Depth dtype must be float32, got {array.dtype}")
    if not np.isfinite(array).all() or array.min() < 0.0 or array.max() > 1.0:
        raise LayerContractError("Depth must contain finite values in [0, 1]")
    if float(array.max() - array.min()) <= np.finfo(np.float32).eps:
        raise LayerContractError("Depth has no usable dynamic range")
    return np.ascontiguousarray(array)


def _gradient_magnitude(values: np.ndarray) -> np.ndarray:
    horizontal = np.zeros_like(values, dtype=np.float32)
    vertical = np.zeros_like(values, dtype=np.float32)
    horizontal_delta = np.abs(values[:, 1:] - values[:, :-1])
    vertical_delta = np.abs(values[1:, :] - values[:-1, :])
    horizontal[:, 1:] = horizontal_delta
    horizontal[:, :-1] = np.maximum(horizontal[:, :-1], horizontal_delta)
    vertical[1:, :] = vertical_delta
    vertical[:-1, :] = np.maximum(vertical[:-1, :], vertical_delta)
    return np.hypot(horizontal, vertical).astype(np.float32, copy=False)


def _normalize_edge(edge: np.ndarray, *, percentile: float) -> np.ndarray:
    scale = float(np.percentile(edge, percentile))
    if scale <= np.finfo(np.float32).eps:
        return np.zeros_like(edge, dtype=np.float32)
    return np.clip(edge / scale, 0.0, 1.0).astype(np.float32, copy=False)


def boundary_strength(
    image: Image.Image,
    depth: np.ndarray,
    *,
    percentile: float,
) -> np.ndarray:
    """Return a normalized union of luminance and depth discontinuities."""

    rgb = np.asarray(image, dtype=np.float32) / 255.0
    luminance = (rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722).astype(
        np.float32, copy=False
    )
    rgb_edge = _normalize_edge(_gradient_magnitude(luminance), percentile=percentile)
    depth_edge = _normalize_edge(_gradient_magnitude(depth), percentile=percentile)
    return np.maximum(rgb_edge, depth_edge).astype(np.float32, copy=False)


def _box_blur_3x3(values: np.ndarray) -> np.ndarray:
    padded = np.pad(values, 1, mode="edge")
    result = np.zeros_like(values, dtype=np.float32)
    height, width = values.shape
    for y_offset in range(3):
        for x_offset in range(3):
            result += padded[y_offset : y_offset + height, x_offset : x_offset + width]
    return result / 9.0


def refine_depth_with_edges(
    depth: np.ndarray,
    edge: np.ndarray,
    *,
    iterations: int,
) -> np.ndarray:
    """Smooth flat regions while retaining original values at strong boundaries."""

    if depth.shape != edge.shape:
        raise LayerContractError("Depth and boundary-strength shapes must match")
    refined = depth.copy()
    for _ in range(iterations):
        blurred = _box_blur_3x3(refined)
        refined = edge * depth + (1.0 - edge) * blurred
    return np.clip(refined, 0.0, 1.0).astype(np.float32, copy=False)


def _weighted_histogram_kmeans(
    values: np.ndarray,
    *,
    bins: int,
    max_iterations: int,
    tolerance: float,
) -> tuple[np.ndarray, int]:
    counts, boundaries = np.histogram(values, bins=bins, range=(0.0, 1.0))
    positions = ((boundaries[:-1] + boundaries[1:]) * 0.5).astype(np.float64)
    weights = counts.astype(np.float64)
    centers = np.quantile(values, [0.1, 0.5, 0.9]).astype(np.float64)
    if np.unique(centers).size != 3:
        centers = np.linspace(float(values.min()), float(values.max()), 3)

    for iteration in range(1, max_iterations + 1):
        assignments = np.argmin(np.abs(positions[:, None] - centers[None, :]), axis=1)
        updated = centers.copy()
        for index in range(3):
            selected = assignments == index
            selected_weight = float(weights[selected].sum())
            if selected_weight <= 0.0:
                raise LayerContractError("Depth distribution produced an empty layer cluster")
            updated[index] = float(
                np.sum(positions[selected] * weights[selected]) / selected_weight
            )
        updated.sort()
        if float(np.max(np.abs(updated - centers))) <= tolerance:
            return updated, iteration
        centers = updated
    raise LayerContractError("Layer clustering did not converge")


def build_layers(
    image: Image.Image,
    depth: np.ndarray,
    *,
    config: LayerBuildConfig | None = None,
) -> LayerBuildResult:
    """Build exhaustive far-to-near labels from relative depth and RGB edges.

    Labels are ``0=background``, ``1=midground``, and ``2=foreground``. They
    describe inferred relative ordering, not semantic classes or metric ranges.
    """

    settings = config or LayerBuildConfig()
    _validate_config(settings)
    validated_depth = _validate_inputs(image, depth)
    edge = boundary_strength(
        image,
        validated_depth,
        percentile=settings.edge_percentile,
    )
    refined = refine_depth_with_edges(
        validated_depth,
        edge,
        iterations=settings.smoothing_iterations,
    )
    centers_array, iterations = _weighted_histogram_kmeans(
        refined,
        bins=settings.histogram_bins,
        max_iterations=settings.max_kmeans_iterations,
        tolerance=settings.convergence_tolerance,
    )
    thresholds = (
        float((centers_array[0] + centers_array[1]) * 0.5),
        float((centers_array[1] + centers_array[2]) * 0.5),
    )
    labels = np.digitize(refined, thresholds, right=False).astype(np.uint8)
    fractions = tuple(float(np.mean(labels == index)) for index in range(3))
    if any(fraction < settings.min_layer_fraction for fraction in fractions):
        raise LayerContractError(
            "At least one inferred layer is smaller than min_layer_fraction; "
            "the three-layer model is unsupported for this image"
        )

    return LayerBuildResult(
        refined_depth=np.ascontiguousarray(refined),
        boundary_strength=np.ascontiguousarray(edge),
        labels=np.ascontiguousarray(labels),
        centers=tuple(float(value) for value in centers_array),
        thresholds=thresholds,
        fractions=fractions,
        iterations=iterations,
    )


def layer_preview(labels: np.ndarray) -> np.ndarray:
    """Map a valid uint8 layer map to the fixed diagnostic RGB palette."""

    if labels.ndim != 2 or labels.dtype != np.uint8:
        raise LayerContractError("Layer preview input must be a 2D uint8 array")
    if labels.size == 0 or labels.min() < 0 or labels.max() > FOREGROUND_LABEL:
        raise LayerContractError("Layer labels must be in the inclusive range [0, 2]")
    return LAYER_PALETTE[labels]
