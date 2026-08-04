"""Typed contracts shared by the depth-baseline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class IngestedImage:
    """A decoded RGB image with its source transforms recorded.

    ``image`` is RGB, top-left-origin, and row-major. Its dimensions are the
    post-EXIF dimensions used by every downstream pixel-aligned artifact.
    """

    image: Image.Image
    source_path: Path
    source_sha256: str
    media_type: str
    source_format: str
    original_width: int
    original_height: int
    exif_orientation: int
    orientation_applied: bool
    color_space: str
    color_transform: str

    @property
    def width(self) -> int:
        return self.image.width

    @property
    def height(self) -> int:
        return self.image.height


@dataclass(frozen=True)
class ModelIdentity:
    """Immutable identity and redistribution facts for a model checkpoint."""

    model_id: str
    revision: str
    backend: str
    upstream_code_license: str
    weights_license: str
    backend_code_license: str
    weights_sha256: str
    weights_bytes: int
    source_url: str


@dataclass(frozen=True)
class InferenceTelemetry:
    """Measured environment and performance values for one prediction."""

    device: str
    device_name: str
    precision: str
    model_load_seconds: float
    inference_seconds: float
    peak_accelerator_memory_bytes: int | None
    package_versions: dict[str, str]
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DepthPrediction:
    """Raw relative proximity scores from a monocular depth model.

    ``values`` must be a finite HxW floating-point array aligned to the input
    RGB image. Values are unitless; larger scores represent nearer content.
    """

    values: np.ndarray
    model: ModelIdentity
    telemetry: InferenceTelemetry


class RelativeDepthEstimator(Protocol):
    """Replaceable interface for monocular relative-depth backends."""

    def predict(self, image: Image.Image, *, seed: int) -> DepthPrediction:
        """Predict an HxW relative proximity map for an RGB image."""
