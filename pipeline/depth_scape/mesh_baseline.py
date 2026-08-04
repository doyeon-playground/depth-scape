"""Orchestration for the continuous relative-depth mesh experiment."""

from __future__ import annotations

import time
from pathlib import Path

from .depth_run import load_depth_run
from .image_io import DEFAULT_MAX_FILE_BYTES, DEFAULT_MAX_PIXELS, load_image
from .mesh import MeshBuildConfig, build_continuous_depth_mesh
from .mesh_artifacts import MeshArtifacts, write_mesh_artifacts


def run_mesh_baseline(
    *,
    input_path: Path,
    depth_run_dir: Path,
    output_dir: Path,
    config: MeshBuildConfig | None = None,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_pixels: int = DEFAULT_MAX_PIXELS,
    overwrite: bool = False,
) -> MeshArtifacts:
    """Validate aligned RGB/depth inputs and export a cut continuous mesh."""

    settings = config or MeshBuildConfig()
    image = load_image(
        input_path,
        max_file_bytes=max_file_bytes,
        max_pixels=max_pixels,
    )
    depth_run = load_depth_run(depth_run_dir, image=image)
    started = time.perf_counter()
    result = build_continuous_depth_mesh(image.image, depth_run.depth, config=settings)
    elapsed_seconds = time.perf_counter() - started
    return write_mesh_artifacts(
        output_dir=output_dir,
        image=image,
        depth_run=depth_run,
        result=result,
        config=settings,
        elapsed_seconds=elapsed_seconds,
        overwrite=overwrite,
    )
