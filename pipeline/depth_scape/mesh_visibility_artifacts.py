"""Artifact writer for bounded continuous-mesh camera evaluation."""

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
from .mesh_run import LoadedMeshRun
from .mesh_visibility import MeshVisibilityConfig, MeshVisibilityPlan

MESH_CAMERA_MANIFEST_FILENAME = "mesh-camera.json"


class MeshVisibilityArtifactError(RuntimeError):
    """Raised when mesh-visibility output would overwrite unsafe targets."""


@dataclass(frozen=True)
class MeshVisibilityArtifacts:
    """Paths created by a completed bounded mesh-camera evaluation."""

    center_view: Path
    left_view: Path
    right_view: Path
    center_geometry_holes: Path
    left_view_holes: Path
    right_view_holes: Path
    all_view_holes: Path
    manifest: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prepare_targets(output_dir: Path, *, overwrite: bool) -> MeshVisibilityArtifacts:
    directory = output_dir.expanduser().resolve()
    if directory.exists() and not directory.is_dir():
        raise MeshVisibilityArtifactError(f"Output path is not a directory: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    artifacts = MeshVisibilityArtifacts(
        center_view=directory / "center-view.png",
        left_view=directory / "left-view.png",
        right_view=directory / "right-view.png",
        center_geometry_holes=directory / "center-geometry-holes.png",
        left_view_holes=directory / "left-view-holes.png",
        right_view_holes=directory / "right-view-holes.png",
        all_view_holes=directory / "all-view-holes.png",
        manifest=directory / MESH_CAMERA_MANIFEST_FILENAME,
    )
    existing = [path for path in artifacts.__dict__.values() if path.exists()]
    if existing and not overwrite:
        names = ", ".join(path.name for path in existing)
        raise MeshVisibilityArtifactError(
            f"Refusing to overwrite existing mesh-camera artifacts ({names}); pass --overwrite"
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


def _view_description(path: Path, values: np.ndarray, *, meaning: str) -> dict[str, object]:
    return {
        "path": path.name,
        "format": "PNG",
        "dtype": "uint8",
        "shape": [int(value) for value in values.shape],
        "meaning": meaning,
        "provenance": "display-only rendering from observed RGB and inferred geometry",
        "sha256": _sha256(path),
    }


def _mask_description(path: Path, mask: np.ndarray, *, meaning: str) -> dict[str, object]:
    return {
        "path": path.name,
        "format": "PNG",
        "dtype": "uint8",
        "shape": [int(value) for value in mask.shape],
        "meaning": meaning,
        "maskValues": {"0": "covered", "255": "uncovered"},
        "coordinateSpace": "render viewport; top-left origin",
        "pixelCount": int(np.count_nonzero(mask)),
        "pixelFraction": float(np.mean(mask)),
        "provenance": "derived from inferred mesh visibility; not generated content",
        "sha256": _sha256(path),
    }


def write_mesh_visibility_artifacts(
    *,
    output_dir: Path,
    mesh: LoadedMeshRun,
    plan: MeshVisibilityPlan,
    config: MeshVisibilityConfig,
    elapsed_seconds: float,
    overwrite: bool,
) -> MeshVisibilityArtifacts:
    """Write endpoint views, uncovered-pixel masks, and camera metadata."""

    artifacts = _prepare_targets(output_dir, overwrite=overwrite)
    _write_png(artifacts.center_view, plan.center_view)
    _write_png(artifacts.left_view, plan.left_view)
    _write_png(artifacts.right_view, plan.right_view)
    _write_mask(artifacts.center_geometry_holes, plan.center_geometry_holes)
    _write_mask(artifacts.left_view_holes, plan.left_view_holes)
    _write_mask(artifacts.right_view_holes, plan.right_view_holes)
    _write_mask(artifacts.all_view_holes, plan.all_view_holes)

    with Image.open(artifacts.center_view) as opened:
        saved_center = np.asarray(opened.convert("RGB")).copy()
    if not np.array_equal(saved_center, plan.center_view):
        raise MeshVisibilityArtifactError("Saved center view changed observed reference pixels")

    artifact_descriptions: dict[str, object] = {
        "centerView": _view_description(
            artifacts.center_view,
            plan.center_view,
            meaning="default viewpoint using the observed texture directly",
        ),
        "leftView": _view_description(
            artifacts.left_view,
            plan.left_view,
            meaning="mesh render at camera position -1 before hidden-content completion",
        ),
        "rightView": _view_description(
            artifacts.right_view,
            plan.right_view,
            meaning="mesh render at camera position +1 before hidden-content completion",
        ),
        "centerGeometryHoles": _mask_description(
            artifacts.center_geometry_holes,
            plan.center_geometry_holes,
            meaning="pixels not covered by retained mesh faces at the source camera position",
        ),
        "leftViewHoles": _mask_description(
            artifacts.left_view_holes,
            plan.left_view_holes,
            meaning="pixels uncovered at camera position -1",
        ),
        "rightViewHoles": _mask_description(
            artifacts.right_view_holes,
            plan.right_view_holes,
            meaning="pixels uncovered at camera position +1",
        ),
        "allViewHoles": _mask_description(
            artifacts.all_view_holes,
            plan.all_view_holes,
            meaning="union of uncovered pixels at sampled non-default camera positions",
        ),
    }
    git_revision, git_dirty = git_state()
    warnings = [
        "The camera uses unitless relative depth and is not a metric reconstruction.",
        "Hole masks identify missing coverage; they do not recover hidden reality.",
        "The center view uses observed RGB directly while mesh-only gaps remain disclosed.",
        "Moving outside the recorded camera range is unsupported.",
        "No generated RGB or generated depth is included in this run.",
    ]
    if git_dirty:
        warnings.append("DepthScape source checkout had uncommitted changes during this run.")

    manifest: dict[str, object] = {
        "schemaVersion": "0.1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "sha256": mesh.source_sha256,
            "sourceDimensions": {"width": mesh.width, "height": mesh.height},
            "renderDimensions": {
                "width": plan.render_width,
                "height": plan.render_height,
            },
            "provenance": "observed RGB identity from the validated mesh run",
        },
        "meshInput": {
            "manifestSha256": mesh.manifest_sha256,
            "algorithmId": mesh.algorithm_id,
            "algorithmVersion": mesh.algorithm_version,
            "vertexCount": int(mesh.vertices.shape[0]),
            "faceCount": int(mesh.faces.shape[0]),
            "provenance": "inferred geometry with observed texture",
        },
        "camera": {
            "model": "orthographic-horizontal-relative-depth",
            "positionRange": [-1.0, 1.0],
            "defaultPosition": 0.0,
            "positionMeaning": "-1=left endpoint, 0=source viewpoint, +1=right endpoint",
            "screenMotion": "near content moves opposite camera direction",
            "maxNearShiftFraction": config.max_near_shift_fraction,
            "maxNearShiftPixelCap": config.max_near_shift_pixels,
            "maxNearShiftPixelsApplied": plan.max_near_shift_pixels,
            "maxFaces": config.max_faces,
            "sampledPositions": list(plan.camera_positions),
            "sampledPositionsOverride": config.sampled_positions,
            "maxSampleShiftStepPixelsRequested": config.max_sample_shift_step_pixels,
            "maxNearShiftStepPixelsObserved": round(
                max(
                    abs(right - left) * plan.max_near_shift_pixels
                    for left, right in zip(
                        plan.camera_positions,
                        plan.camera_positions[1:],
                    )
                ),
                6,
            ),
            "samplingLimitation": "finite sampled positions; not a continuous-path proof",
            "renderer": "deterministic CPU triangle rasterizer with larger-relative-Z-wins buffer",
        },
        "result": {
            "defaultViewPixelIdenticalAtRenderResolution": plan.default_view_pixel_identical,
            "centerGeometryHolePixels": int(np.count_nonzero(plan.center_geometry_holes)),
            "leftViewHolePixels": int(np.count_nonzero(plan.left_view_holes)),
            "rightViewHolePixels": int(np.count_nonzero(plan.right_view_holes)),
            "allViewHolePixels": int(np.count_nonzero(plan.all_view_holes)),
        },
        "coordinateSystem": {
            "viewportOrigin": "top-left",
            "xAxis": "right",
            "yAxis": "down",
            "depthTest": "larger relative proximity is nearer",
            "arrayOrder": "row-major (height, width)",
        },
        "artifacts": artifact_descriptions,
        "performance": {
            "totalPlanningSeconds": elapsed_seconds,
            "renderSecondsByPosition": [
                {"position": position, "seconds": seconds}
                for position, seconds in zip(
                    plan.camera_positions,
                    plan.render_seconds,
                    strict=True,
                )
            ],
        },
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
