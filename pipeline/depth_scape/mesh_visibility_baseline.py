"""Orchestration for bounded continuous-mesh camera evaluation."""

from __future__ import annotations

import time
from pathlib import Path

from .mesh_run import load_mesh_run
from .mesh_visibility import MeshVisibilityConfig, plan_mesh_visibility
from .mesh_visibility_artifacts import (
    MeshVisibilityArtifacts,
    write_mesh_visibility_artifacts,
)


def run_mesh_visibility_baseline(
    *,
    mesh_run_dir: Path,
    output_dir: Path,
    config: MeshVisibilityConfig | None = None,
    overwrite: bool = False,
) -> MeshVisibilityArtifacts:
    """Validate a mesh run and export bounded camera views and hole masks."""

    settings = config or MeshVisibilityConfig()
    mesh = load_mesh_run(mesh_run_dir)
    started = time.perf_counter()
    plan = plan_mesh_visibility(mesh, config=settings)
    elapsed_seconds = time.perf_counter() - started
    return write_mesh_visibility_artifacts(
        output_dir=output_dir,
        mesh=mesh,
        plan=plan,
        config=settings,
        elapsed_seconds=elapsed_seconds,
        overwrite=overwrite,
    )
