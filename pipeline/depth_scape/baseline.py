"""Orchestration for the reproducible relative-depth baseline."""

from __future__ import annotations

from pathlib import Path

from .artifacts import DepthArtifacts, write_depth_artifacts
from .contracts import RelativeDepthEstimator
from .depth import normalize_relative_depth
from .image_io import DEFAULT_MAX_FILE_BYTES, DEFAULT_MAX_PIXELS, load_image


def run_depth_baseline(
    *,
    input_path: Path,
    output_dir: Path,
    estimator: RelativeDepthEstimator,
    seed: int = 0,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_pixels: int = DEFAULT_MAX_PIXELS,
    overwrite: bool = False,
) -> DepthArtifacts:
    """Run ingestion, relative-depth inference, validation, and artifact export."""

    image = load_image(
        input_path,
        max_file_bytes=max_file_bytes,
        max_pixels=max_pixels,
    )
    prediction = estimator.predict(image.image, seed=seed)
    normalized, raw_min, raw_max = normalize_relative_depth(
        prediction.values,
        expected_height=image.height,
        expected_width=image.width,
    )
    return write_depth_artifacts(
        output_dir=output_dir,
        image=image,
        depth=normalized,
        raw_min=raw_min,
        raw_max=raw_max,
        prediction=prediction,
        seed=seed,
        max_file_bytes=max_file_bytes,
        max_pixels=max_pixels,
        overwrite=overwrite,
    )
