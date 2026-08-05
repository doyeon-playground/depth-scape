"""Reproducible baseline runner for hidden-surface request planning."""

from __future__ import annotations

import time
from pathlib import Path

from .hidden_surface import (
    HiddenSurfaceConfig,
    plan_hidden_surfaces,
    validate_hidden_surface_config,
)
from .hidden_surface_artifacts import (
    HiddenSurfaceArtifacts,
    write_hidden_surface_artifacts,
)
from .mesh_run import load_mesh_run
from .mesh_visibility import MeshVisibilityConfig, plan_mesh_visibility


def run_hidden_surface_baseline(
    *,
    mesh_run_dir: Path,
    output_dir: Path,
    visibility_config: MeshVisibilityConfig,
    hidden_surface_config: HiddenSurfaceConfig,
    overwrite: bool = False,
) -> HiddenSurfaceArtifacts:
    """Load a mesh, map bounded view holes, and write the request contract."""

    started = time.perf_counter()
    validate_hidden_surface_config(hidden_surface_config)
    mesh = load_mesh_run(mesh_run_dir)
    visibility = plan_mesh_visibility(mesh, config=visibility_config)
    plan = plan_hidden_surfaces(visibility, config=hidden_surface_config)
    return write_hidden_surface_artifacts(
        output_dir=output_dir,
        mesh=mesh,
        visibility=visibility,
        visibility_config=visibility_config,
        plan=plan,
        config=hidden_surface_config,
        elapsed_seconds=time.perf_counter() - started,
        overwrite=overwrite,
    )
