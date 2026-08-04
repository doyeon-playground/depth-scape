"""Orchestration for bounded camera and disocclusion planning."""

from __future__ import annotations

import time
from pathlib import Path

from .layer_run import load_layer_run
from .visibility import VisibilityConfig, plan_visibility
from .visibility_artifacts import VisibilityArtifacts, write_visibility_artifacts


def run_visibility_baseline(
    *,
    layer_run_dir: Path,
    output_dir: Path,
    config: VisibilityConfig | None = None,
    overwrite: bool = False,
) -> VisibilityArtifacts:
    """Validate a layer run and export its bounded horizontal camera plan."""

    settings = config or VisibilityConfig()
    layer_run = load_layer_run(layer_run_dir)
    started = time.perf_counter()
    plan = plan_visibility(layer_run.labels, config=settings)
    elapsed_seconds = time.perf_counter() - started
    return write_visibility_artifacts(
        output_dir=output_dir,
        layer_run=layer_run,
        plan=plan,
        config=settings,
        elapsed_seconds=elapsed_seconds,
        overwrite=overwrite,
    )
