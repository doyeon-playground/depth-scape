"""Writers for the first relative-depth artifact contract."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from . import __version__
from .contracts import DepthPrediction, IngestedImage
from .depth import depth_preview

DEPTH_FILENAME = "relative-depth.npy"
PREVIEW_FILENAME = "depth-preview.png"
MANIFEST_FILENAME = "run.json"


class ArtifactWriteError(RuntimeError):
    """Raised when output would be unsafe or overwrite existing artifacts."""


@dataclass(frozen=True)
class DepthArtifacts:
    """Paths created by a completed depth-baseline run."""

    depth: Path
    preview: Path
    manifest: Path


def git_state() -> tuple[str | None, bool | None]:
    """Return the source checkout revision and dirtiness when Git is available."""

    repository = Path(__file__).resolve().parents[2]
    try:
        revision_result = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
        if revision_result.returncode != 0:
            return None, None
        status_result = subprocess.run(
            ["git", "-C", str(repository), "status", "--porcelain"],
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    dirty = None if status_result.returncode != 0 else bool(status_result.stdout.strip())
    return revision_result.stdout.strip(), dirty


def _prepare_targets(output_dir: Path, *, overwrite: bool) -> DepthArtifacts:
    directory = output_dir.expanduser().resolve()
    if directory.exists() and not directory.is_dir():
        raise ArtifactWriteError(f"Output path is not a directory: {directory}")
    directory.mkdir(parents=True, exist_ok=True)

    artifacts = DepthArtifacts(
        depth=directory / DEPTH_FILENAME,
        preview=directory / PREVIEW_FILENAME,
        manifest=directory / MANIFEST_FILENAME,
    )
    existing = [path for path in artifacts.__dict__.values() if path.exists()]
    if existing and not overwrite:
        names = ", ".join(path.name for path in existing)
        raise ArtifactWriteError(
            f"Refusing to overwrite existing artifacts ({names}); pass --overwrite"
        )
    return artifacts


def _write_depth(path: Path, depth: np.ndarray) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("wb") as stream:
            np.save(stream, depth, allow_pickle=False)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_preview(path: Path, depth: np.ndarray) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        Image.fromarray(depth_preview(depth), mode="L").save(temporary, format="PNG")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_depth_artifacts(
    *,
    output_dir: Path,
    image: IngestedImage,
    depth: np.ndarray,
    raw_min: float,
    raw_max: float,
    prediction: DepthPrediction,
    seed: int,
    max_file_bytes: int,
    max_pixels: int,
    overwrite: bool,
) -> DepthArtifacts:
    """Write aligned numeric depth, a display preview, and reproducibility data."""

    artifacts = _prepare_targets(output_dir, overwrite=overwrite)
    model = prediction.model
    telemetry = prediction.telemetry
    git_revision, git_dirty = git_state()
    warnings = [
        "Relative depth is unitless and must not be interpreted as metric distance.",
        "Every value in the depth artifact is inferred from the observed RGB image.",
        *telemetry.warnings,
    ]
    if git_dirty:
        warnings.append("DepthScape source checkout had uncommitted changes during this run.")
    manifest: dict[str, object] = {
        "schemaVersion": "0.1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "fileName": image.source_path.name,
            "sha256": image.source_sha256,
            "mediaType": image.media_type,
            "format": image.source_format,
            "originalDimensions": {
                "width": image.original_width,
                "height": image.original_height,
            },
            "normalizedDimensions": {"width": image.width, "height": image.height},
            "exifOrientation": image.exif_orientation,
            "orientationApplied": image.orientation_applied,
            "colorSpace": image.color_space,
            "colorTransform": image.color_transform,
            "provenance": "observed",
        },
        "model": {
            "id": model.model_id,
            "revision": model.revision,
            "backend": model.backend,
            "source": model.source_url,
            "licenses": {
                "upstreamCode": model.upstream_code_license,
                "weights": model.weights_license,
                "backendCode": model.backend_code_license,
            },
            "weights": {
                "file": "model.safetensors",
                "sha256": model.weights_sha256,
                "bytes": model.weights_bytes,
            },
        },
        "configuration": {
            "seed": seed,
            "device": telemetry.device,
            "precision": telemetry.precision,
            "deterministicAlgorithmsRequested": True,
            "maxFileBytes": max_file_bytes,
            "maxPixels": max_pixels,
        },
        "coordinateSystem": {
            "origin": "top-left",
            "xAxis": "right",
            "yAxis": "down",
            "arrayOrder": "row-major (height, width)",
        },
        "artifacts": {
            "relativeDepth": {
                "path": artifacts.depth.name,
                "format": "NumPy NPY",
                "dtype": "float32",
                "shape": [image.height, image.width],
                "range": [0.0, 1.0],
                "meaning": "unitless relative proximity; larger is nearer",
                "provenance": "inferred",
                "rawRangeBeforeNormalization": [raw_min, raw_max],
            },
            "preview": {
                "path": artifacts.preview.name,
                "format": "PNG",
                "dtype": "uint8",
                "range": [0, 255],
                "meaning": "display only; white is near and black is far",
            },
        },
        "performance": {
            "modelLoadSeconds": telemetry.model_load_seconds,
            "inferenceSeconds": telemetry.inference_seconds,
            "peakAcceleratorMemoryBytes": telemetry.peak_accelerator_memory_bytes,
            "deviceName": telemetry.device_name,
        },
        "software": {
            "depthScape": {
                "version": __version__,
                "gitRevision": git_revision,
                "gitDirty": git_dirty,
            },
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": telemetry.package_versions,
        },
        "warnings": warnings,
    }

    _write_depth(artifacts.depth, depth)
    _write_preview(artifacts.preview, depth)
    _write_manifest(artifacts.manifest, manifest)
    return artifacts
