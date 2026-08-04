"""Artifact writer for bounded camera and disocclusion planning."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from . import __version__
from .artifacts import git_state
from .layer_run import LoadedLayerRun
from .visibility import VisibilityConfig, VisibilityPlan, disocclusion_preview

CAMERA_MANIFEST_FILENAME = "camera-plan.json"


class VisibilityArtifactError(RuntimeError):
    """Raised when planning output would overwrite or target unsafe paths."""


@dataclass(frozen=True)
class VisibilityArtifacts:
    """Paths created by a completed visibility-planning run."""

    background_disocclusion: Path
    midground_disocclusion: Path
    all_view_holes: Path
    left_view_holes: Path
    right_view_holes: Path
    preview: Path
    manifest: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prepare_targets(output_dir: Path, *, overwrite: bool) -> VisibilityArtifacts:
    directory = output_dir.expanduser().resolve()
    if directory.exists() and not directory.is_dir():
        raise VisibilityArtifactError(f"Output path is not a directory: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    artifacts = VisibilityArtifacts(
        background_disocclusion=directory / "background-disocclusion-mask.png",
        midground_disocclusion=directory / "midground-disocclusion-mask.png",
        all_view_holes=directory / "all-view-holes.png",
        left_view_holes=directory / "left-view-holes.png",
        right_view_holes=directory / "right-view-holes.png",
        preview=directory / "disocclusion-preview.png",
        manifest=directory / CAMERA_MANIFEST_FILENAME,
    )
    existing = [path for path in artifacts.__dict__.values() if path.exists()]
    if existing and not overwrite:
        names = ", ".join(path.name for path in existing)
        raise VisibilityArtifactError(
            f"Refusing to overwrite existing visibility artifacts ({names}); pass --overwrite"
        )
    return artifacts


def _write_png(path: Path, values: np.ndarray) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        Image.fromarray(values).save(temporary, format="PNG")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_mask(path: Path, mask: np.ndarray) -> None:
    _write_png(path, np.where(mask, 255, 0).astype(np.uint8))


def _write_json(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _mask_description(
    path: Path,
    mask: np.ndarray,
    *,
    coordinate_space: str,
    meaning: str,
) -> dict[str, object]:
    return {
        "path": path.name,
        "format": "PNG",
        "dtype": "uint8",
        "shape": [int(mask.shape[0]), int(mask.shape[1])],
        "meaning": meaning,
        "maskValues": {"0": "excluded", "255": "included"},
        "coordinateSpace": coordinate_space,
        "pixelCount": int(np.count_nonzero(mask)),
        "pixelFraction": float(np.mean(mask)),
        "sha256": _sha256(path),
    }


def write_visibility_artifacts(
    *,
    output_dir: Path,
    layer_run: LoadedLayerRun,
    plan: VisibilityPlan,
    config: VisibilityConfig,
    elapsed_seconds: float,
    overwrite: bool,
) -> VisibilityArtifacts:
    """Write completion masks, endpoint diagnostics, and the camera contract."""

    artifacts = _prepare_targets(output_dir, overwrite=overwrite)
    _write_mask(artifacts.background_disocclusion, plan.background_disocclusion)
    _write_mask(artifacts.midground_disocclusion, plan.midground_disocclusion)
    _write_mask(artifacts.all_view_holes, plan.all_view_holes)
    _write_mask(artifacts.left_view_holes, plan.left_view_holes)
    _write_mask(artifacts.right_view_holes, plan.right_view_holes)
    _write_png(artifacts.preview, disocclusion_preview(plan))

    artifact_descriptions: dict[str, object] = {
        "backgroundDisocclusionMask": _mask_description(
            artifacts.background_disocclusion,
            plan.background_disocclusion,
            coordinate_space="background source grid",
            meaning="background pixels to complete behind nearer layers",
        ),
        "midgroundDisocclusionMask": _mask_description(
            artifacts.midground_disocclusion,
            plan.midground_disocclusion,
            coordinate_space="midground source grid",
            meaning="midground pixels to complete behind the foreground layer",
        ),
        "allViewHoles": _mask_description(
            artifacts.all_view_holes,
            plan.all_view_holes,
            coordinate_space="output viewport union across the supported path",
            meaning="pixels exposed by at least one sampled camera position before completion",
        ),
        "leftViewHoles": _mask_description(
            artifacts.left_view_holes,
            plan.left_view_holes,
            coordinate_space="output viewport at camera position -1",
            meaning="pixels exposed at the left camera endpoint before completion",
        ),
        "rightViewHoles": _mask_description(
            artifacts.right_view_holes,
            plan.right_view_holes,
            coordinate_space="output viewport at camera position +1",
            meaning="pixels exposed at the right camera endpoint before completion",
        ),
        "preview": {
            "path": artifacts.preview.name,
            "format": "PNG",
            "meaning": "display only; target-layer completion overlap diagnostic",
            "palette": {
                "none": [0, 0, 0],
                "backgroundOnly": [65, 105, 225],
                "midgroundOnly": [242, 186, 73],
                "bothTargetLayers": [190, 74, 130],
            },
            "sha256": _sha256(artifacts.preview),
        },
    }
    git_revision, git_dirty = git_state()
    warnings = [
        "Camera positions and parallax shifts are discrete pixel-space planning values.",
        "The camera plan is not a physical camera model and has no metric units.",
        "Disocclusion masks identify missing content; they do not recover hidden reality.",
        "Moving outside the recorded range is unsupported.",
    ]
    if git_dirty:
        warnings.append("DepthScape source checkout had uncommitted changes during this run.")

    manifest: dict[str, object] = {
        "schemaVersion": "0.1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "sha256": layer_run.source_sha256,
            "dimensions": {"width": layer_run.width, "height": layer_run.height},
            "provenance": "observed identity only; source pixels are not copied here",
        },
        "layerInput": {
            "artifactSha256": layer_run.layer_map_sha256,
            "manifestSha256": layer_run.manifest_sha256,
            "algorithmId": layer_run.algorithm_id,
            "algorithmVersion": layer_run.algorithm_version,
            "provenance": "inferred",
        },
        "camera": {
            "model": "discrete-horizontal-layer-translation",
            "positionRange": [-1.0, 1.0],
            "defaultPosition": 0.0,
            "positionMeaning": "-1=left endpoint, 0=source viewpoint, +1=right endpoint",
            "screenShiftConvention": "positive pixels move content right",
            "maxForegroundShiftFraction": config.max_foreground_shift_fraction,
            "maxForegroundShiftPixelCap": config.max_foreground_shift_pixels,
            "maxForegroundShiftPixelsApplied": plan.max_foreground_shift_pixels,
            "layerParallaxFactorsFarToNear": list(plan.layer_parallax_factors),
            "sampledPositions": plan.sampled_positions,
            "sampling": "every integer foreground screen shift in the applied range",
        },
        "coordinateSystem": {
            "origin": "top-left",
            "xAxis": "right",
            "yAxis": "down",
            "arrayOrder": "row-major (height, width)",
        },
        "artifacts": artifact_descriptions,
        "performance": {"planningSeconds": elapsed_seconds},
        "software": {
            "depthScape": {
                "version": __version__,
                "gitRevision": git_revision,
                "gitDirty": git_dirty,
            },
            "python": sys.version.split()[0],
            "numpy": np.__version__,
        },
        "warnings": warnings,
    }
    _write_json(artifacts.manifest, manifest)
    return artifacts
