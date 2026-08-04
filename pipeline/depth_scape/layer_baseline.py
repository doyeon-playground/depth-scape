"""Orchestration for the provisional three-layer baseline."""

from __future__ import annotations

import time
from pathlib import Path

from .depth_run import load_depth_run
from .image_io import DEFAULT_MAX_FILE_BYTES, DEFAULT_MAX_PIXELS, load_image
from .layer_artifacts import LayerArtifacts, write_layer_artifacts
from .layers import LayerBuildConfig, build_layers


def run_layer_baseline(
    *,
    input_path: Path,
    depth_run_dir: Path,
    output_dir: Path,
    config: LayerBuildConfig | None = None,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_pixels: int = DEFAULT_MAX_PIXELS,
    overwrite: bool = False,
) -> LayerArtifacts:
    """Validate aligned RGB/depth inputs and export three inferred layer masks."""

    settings = config or LayerBuildConfig()
    image = load_image(
        input_path,
        max_file_bytes=max_file_bytes,
        max_pixels=max_pixels,
    )
    depth_run = load_depth_run(depth_run_dir, image=image)
    started = time.perf_counter()
    result = build_layers(image.image, depth_run.depth, config=settings)
    elapsed_seconds = time.perf_counter() - started
    return write_layer_artifacts(
        output_dir=output_dir,
        image=image,
        depth_run=depth_run,
        result=result,
        config=settings,
        elapsed_seconds=elapsed_seconds,
        overwrite=overwrite,
    )
