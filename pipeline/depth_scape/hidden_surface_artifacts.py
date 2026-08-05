"""Artifact writer for canonical hidden-surface generation requests."""

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
from .hidden_surface import HiddenSurfaceConfig, HiddenSurfacePlan
from .mesh_run import LoadedMeshRun
from .mesh_visibility import MeshVisibilityConfig, MeshVisibilityPlan

HIDDEN_SURFACE_MANIFEST_FILENAME = "hidden-surface-plan.json"


class HiddenSurfaceArtifactError(RuntimeError):
    """Raised when hidden-surface artifacts cannot be written safely."""


@dataclass(frozen=True)
class HiddenSurfaceArtifacts:
    """Paths created by a completed hidden-surface planning run."""

    request_mask: Path
    relative_depth_hint: Path
    max_relative_depth_exclusive: Path
    request_observation_count: Path
    mapped_view_holes: Path
    border_view_holes: Path
    ambiguous_depth_view_holes: Path
    unresolved_view_holes: Path
    preview: Path
    manifest: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prepare_targets(output_dir: Path, *, overwrite: bool) -> HiddenSurfaceArtifacts:
    directory = output_dir.expanduser().resolve()
    if directory.exists() and not directory.is_dir():
        raise HiddenSurfaceArtifactError(f"Output path is not a directory: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    artifacts = HiddenSurfaceArtifacts(
        request_mask=directory / "hidden-surface-mask.png",
        relative_depth_hint=directory / "hidden-relative-depth-hint.npy",
        max_relative_depth_exclusive=directory / "hidden-depth-ceiling.npy",
        request_observation_count=directory / "hidden-request-observation-count.npy",
        mapped_view_holes=directory / "mapped-view-holes.png",
        border_view_holes=directory / "border-view-holes.png",
        ambiguous_depth_view_holes=directory / "ambiguous-depth-view-holes.png",
        unresolved_view_holes=directory / "unresolved-view-holes.png",
        preview=directory / "hidden-surface-preview.png",
        manifest=directory / HIDDEN_SURFACE_MANIFEST_FILENAME,
    )
    existing = [path for path in artifacts.__dict__.values() if path.exists()]
    if existing and not overwrite:
        names = ", ".join(path.name for path in existing)
        raise HiddenSurfaceArtifactError(
            f"Refusing to overwrite existing hidden-surface artifacts ({names}); pass --overwrite"
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


def _write_array(path: Path, values: np.ndarray) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("wb") as stream:
            np.save(stream, values, allow_pickle=False)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


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


def _preview(center_view: np.ndarray, request_mask: np.ndarray) -> np.ndarray:
    preview = center_view.copy()
    tint = np.array([255.0, 64.0, 192.0], dtype=np.float32)
    preview[request_mask] = np.rint(
        preview[request_mask].astype(np.float32) * np.float32(0.35) + tint * np.float32(0.65)
    ).astype(np.uint8)
    return np.ascontiguousarray(preview)


def _artifact_description(
    path: Path,
    values: np.ndarray,
    *,
    meaning: str,
    coordinate_space: str,
) -> dict[str, object]:
    return {
        "path": path.name,
        "format": path.suffix.removeprefix(".").upper(),
        "dtype": str(values.dtype),
        "shape": [int(value) for value in values.shape],
        "meaning": meaning,
        "coordinateSpace": coordinate_space,
        "sha256": _sha256(path),
    }


def write_hidden_surface_artifacts(
    *,
    output_dir: Path,
    mesh: LoadedMeshRun,
    visibility: MeshVisibilityPlan,
    visibility_config: MeshVisibilityConfig,
    plan: HiddenSurfacePlan,
    config: HiddenSurfaceConfig,
    elapsed_seconds: float,
    overwrite: bool,
) -> HiddenSurfaceArtifacts:
    """Write coupled generation masks, depth constraints, and provenance."""

    artifacts = _prepare_targets(output_dir, overwrite=overwrite)
    _write_mask(artifacts.request_mask, plan.request_mask)
    _write_array(artifacts.relative_depth_hint, plan.relative_depth_hint)
    _write_array(
        artifacts.max_relative_depth_exclusive,
        plan.max_relative_depth_exclusive,
    )
    _write_array(
        artifacts.request_observation_count,
        plan.request_observation_count,
    )
    _write_mask(artifacts.mapped_view_holes, plan.all_mapped_view_holes)
    _write_mask(artifacts.border_view_holes, plan.all_border_view_holes)
    _write_mask(
        artifacts.ambiguous_depth_view_holes,
        plan.all_ambiguous_depth_view_holes,
    )
    _write_mask(artifacts.unresolved_view_holes, plan.all_unresolved_view_holes)
    preview = _preview(visibility.center_view, plan.request_mask)
    _write_png(artifacts.preview, preview)

    coordinate_space = (
        "canonical hidden-surface grid aligned to the default render view; "
        "stored separately from observed RGB"
    )
    artifact_descriptions: dict[str, object] = {
        "requestMask": {
            **_artifact_description(
                artifacts.request_mask,
                plan.request_mask,
                meaning="pixels requiring coupled generated RGB and relative depth",
                coordinate_space=coordinate_space,
            ),
            "maskValues": {"0": "excluded", "255": "generation requested"},
            "pixelCount": int(np.count_nonzero(plan.request_mask)),
        },
        "relativeDepthHint": {
            **_artifact_description(
                artifacts.relative_depth_hint,
                plan.relative_depth_hint,
                meaning="inferred far-side relative-depth hint; NaN outside requestMask",
                coordinate_space=coordinate_space,
            ),
            "numericRange": "[0, 1] inside requestMask",
            "provenance": "inferred from visible mesh depth; not generated depth",
        },
        "maxRelativeDepthExclusive": {
            **_artifact_description(
                artifacts.max_relative_depth_exclusive,
                plan.max_relative_depth_exclusive,
                meaning="generated depth must be smaller to remain behind the occluder",
                coordinate_space=coordinate_space,
            ),
            "numericRange": "(0, 1] inside requestMask",
            "provenance": "inferred from visible occluder depth",
        },
        "requestObservationCount": _artifact_description(
            artifacts.request_observation_count,
            plan.request_observation_count,
            meaning="number of sampled viewport holes mapped to each request pixel",
            coordinate_space=coordinate_space,
        ),
        "mappedViewHoles": {
            **_artifact_description(
                artifacts.mapped_view_holes,
                plan.all_mapped_view_holes,
                meaning="viewport holes represented by the canonical request",
                coordinate_space="union of sampled non-default render viewports",
            ),
            "pixelCount": int(np.count_nonzero(plan.all_mapped_view_holes)),
        },
        "borderViewHoles": {
            **_artifact_description(
                artifacts.border_view_holes,
                plan.all_border_view_holes,
                meaning="viewport-edge holes requiring outpainting rather than disocclusion fill",
                coordinate_space="union of sampled non-default render viewports",
            ),
            "pixelCount": int(np.count_nonzero(plan.all_border_view_holes)),
        },
        "ambiguousDepthViewHoles": {
            **_artifact_description(
                artifacts.ambiguous_depth_view_holes,
                plan.all_ambiguous_depth_view_holes,
                meaning="interior holes without the expected near-to-far depth ordering",
                coordinate_space="union of sampled non-default render viewports",
            ),
            "pixelCount": int(np.count_nonzero(plan.all_ambiguous_depth_view_holes)),
        },
        "unresolvedViewHoles": {
            **_artifact_description(
                artifacts.unresolved_view_holes,
                plan.all_unresolved_view_holes,
                meaning="viewport holes without a safe canonical hidden-surface mapping",
                coordinate_space="union of sampled non-default render viewports",
            ),
            "pixelCount": int(np.count_nonzero(plan.all_unresolved_view_holes)),
        },
        "preview": _artifact_description(
            artifacts.preview,
            preview,
            meaning="display-only magenta overlay of canonical request pixels",
            coordinate_space="default render view",
        ),
    }
    git_revision, git_dirty = git_state()
    warnings = [
        "This plan requests generated RGB and generated relative depth; it does not contain either.",
        "Generated hidden surfaces are plausible synthesis, not recovered reality.",
        "Unresolved viewport holes are outside the generation contract and must limit camera motion.",
        "Depth is unitless relative proximity; larger values are nearer.",
        "Finite sampled positions do not prove coverage for every continuous camera position.",
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
                "width": visibility.render_width,
                "height": visibility.render_height,
            },
            "observedRgbModified": False,
        },
        "meshInput": {
            "manifestSha256": mesh.manifest_sha256,
            "algorithmId": mesh.algorithm_id,
            "algorithmVersion": mesh.algorithm_version,
            "provenance": "inferred geometry with separate observed RGB texture",
        },
        "generationRequest": {
            "requiredChannels": list(plan.required_generated_channels),
            "coupling": "RGB and relative depth must use the exact same requestMask",
            "coordinateSpace": coordinate_space,
            "observedContentPolicy": "generated values are stored on a separate hidden surface",
            "depthOrdering": "generated depth must be less than maxRelativeDepthExclusive",
            "minDepthSeparation": config.min_depth_separation,
            "maxRequestPixels": config.max_request_pixels,
        },
        "camera": {
            "model": "orthographic-horizontal-relative-depth",
            "positionRange": [-1.0, 1.0],
            "sampledPositions": list(plan.camera_positions),
            "maxNearShiftPixelsApplied": visibility.max_near_shift_pixels,
            "maxNearShiftFraction": visibility_config.max_near_shift_fraction,
            "samplingLimitation": "finite sampled positions; not a continuous-path proof",
        },
        "result": {
            "requestPixels": int(np.count_nonzero(plan.request_mask)),
            "mappedViewportHolePixels": int(np.count_nonzero(plan.all_mapped_view_holes)),
            "borderViewportHolePixels": int(np.count_nonzero(plan.all_border_view_holes)),
            "ambiguousDepthViewportHolePixels": int(
                np.count_nonzero(plan.all_ambiguous_depth_view_holes)
            ),
            "unresolvedViewportHolePixels": int(np.count_nonzero(plan.all_unresolved_view_holes)),
            "allSampledHolesMapped": not plan.all_unresolved_view_holes.any(),
            "readyForConfiguredCameraAfterGeneration": not plan.all_unresolved_view_holes.any(),
        },
        "coordinateSystem": {
            "origin": "top-left",
            "xAxis": "right",
            "yAxis": "down",
            "arrayOrder": "row-major (height, width)",
            "relativeDepth": "float32 in [0, 1], larger is nearer",
        },
        "artifacts": artifact_descriptions,
        "performance": {"planningSecondsIncludingVisibility": elapsed_seconds},
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
