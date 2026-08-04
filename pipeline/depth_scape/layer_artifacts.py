"""Writers for the provisional three-layer artifact contract."""

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
from .contracts import IngestedImage
from .depth_run import LoadedDepthRun
from .layers import LAYER_NAMES, LAYER_PALETTE, LayerBuildConfig, LayerBuildResult, layer_preview

LAYER_DEPTH_FILENAME = "layer-depth.npy"
BOUNDARY_STRENGTH_FILENAME = "boundary-strength.npy"
LAYER_MAP_FILENAME = "layer-map.npy"
LAYER_PREVIEW_FILENAME = "layer-preview.png"
LAYER_MANIFEST_FILENAME = "layers.json"


class LayerArtifactError(RuntimeError):
    """Raised when layer output would be unsafe or overwrite existing artifacts."""


@dataclass(frozen=True)
class LayerArtifacts:
    """Paths created by a completed layer-baseline run."""

    refined_depth: Path
    boundary_strength: Path
    layer_map: Path
    preview: Path
    background_mask: Path
    midground_mask: Path
    foreground_mask: Path
    manifest: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prepare_targets(output_dir: Path, *, overwrite: bool) -> LayerArtifacts:
    directory = output_dir.expanduser().resolve()
    if directory.exists() and not directory.is_dir():
        raise LayerArtifactError(f"Output path is not a directory: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    artifacts = LayerArtifacts(
        refined_depth=directory / LAYER_DEPTH_FILENAME,
        boundary_strength=directory / BOUNDARY_STRENGTH_FILENAME,
        layer_map=directory / LAYER_MAP_FILENAME,
        preview=directory / LAYER_PREVIEW_FILENAME,
        background_mask=directory / "background-mask.png",
        midground_mask=directory / "midground-mask.png",
        foreground_mask=directory / "foreground-mask.png",
        manifest=directory / LAYER_MANIFEST_FILENAME,
    )
    existing = [path for path in artifacts.__dict__.values() if path.exists()]
    if existing and not overwrite:
        names = ", ".join(path.name for path in existing)
        raise LayerArtifactError(
            f"Refusing to overwrite existing layer artifacts ({names}); pass --overwrite"
        )
    return artifacts


def _write_npy(path: Path, values: np.ndarray) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("wb") as stream:
            np.save(stream, values, allow_pickle=False)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_png(path: Path, values: np.ndarray) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        Image.fromarray(values).save(temporary, format="PNG")
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


def write_layer_artifacts(
    *,
    output_dir: Path,
    image: IngestedImage,
    depth_run: LoadedDepthRun,
    result: LayerBuildResult,
    config: LayerBuildConfig,
    elapsed_seconds: float,
    overwrite: bool,
) -> LayerArtifacts:
    """Write inferred layers, masks, diagnostics, and reproducibility metadata."""

    artifacts = _prepare_targets(output_dir, overwrite=overwrite)
    _write_npy(artifacts.refined_depth, result.refined_depth)
    _write_npy(artifacts.boundary_strength, result.boundary_strength)
    _write_npy(artifacts.layer_map, result.labels)
    _write_png(artifacts.preview, layer_preview(result.labels))

    masks = []
    mask_paths = (
        artifacts.background_mask,
        artifacts.midground_mask,
        artifacts.foreground_mask,
    )
    for label, path in enumerate(mask_paths):
        mask = np.where(result.labels == label, 255, 0).astype(np.uint8)
        _write_png(path, mask)
        masks.append(
            {
                "path": path.name,
                "label": label,
                "name": LAYER_NAMES[label],
                "dtype": "uint8",
                "meaning": "255=included, 0=excluded",
                "sha256": _sha256(path),
            }
        )

    git_revision, git_dirty = git_state()
    warnings = [
        "Layers are inferred relative-depth groups, not semantic segmentation.",
        "Layer labels are ordered far to near and do not represent metric distance.",
        "Sky and distant geometry can share one background layer.",
    ]
    if git_dirty:
        warnings.append("DepthScape source checkout had uncommitted changes during this run.")

    artifact_descriptions: dict[str, object] = {
        "layerDepth": {
            "path": artifacts.refined_depth.name,
            "format": "NumPy NPY",
            "dtype": "float32",
            "shape": [image.height, image.width],
            "range": [0.0, 1.0],
            "meaning": "edge-preserving depth used only for layer assignment",
            "sha256": _sha256(artifacts.refined_depth),
        },
        "boundaryStrength": {
            "path": artifacts.boundary_strength.name,
            "format": "NumPy NPY",
            "dtype": "float32",
            "shape": [image.height, image.width],
            "range": [0.0, 1.0],
            "meaning": "normalized union of RGB luminance and depth discontinuities",
            "sha256": _sha256(artifacts.boundary_strength),
        },
        "layerMap": {
            "path": artifacts.layer_map.name,
            "format": "NumPy NPY",
            "dtype": "uint8",
            "shape": [image.height, image.width],
            "labels": {str(index): name for index, name in enumerate(LAYER_NAMES)},
            "provenance": "inferred",
            "sha256": _sha256(artifacts.layer_map),
        },
        "preview": {
            "path": artifacts.preview.name,
            "format": "PNG",
            "meaning": "display only",
            "palette": {
                LAYER_NAMES[index]: [int(channel) for channel in LAYER_PALETTE[index]]
                for index in range(3)
            },
            "sha256": _sha256(artifacts.preview),
        },
        "masks": masks,
    }
    manifest: dict[str, object] = {
        "schemaVersion": "0.1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "sha256": image.source_sha256,
            "dimensions": {"width": image.width, "height": image.height},
            "colorSpace": image.color_space,
            "provenance": "observed",
        },
        "depthInput": {
            "artifactSha256": depth_run.depth_sha256,
            "manifestSha256": depth_run.manifest_sha256,
            "modelId": depth_run.model_id,
            "modelRevision": depth_run.model_revision,
            "meaning": "unitless relative proximity; larger is nearer",
            "provenance": "inferred",
        },
        "algorithm": {
            "id": "edge-preserving-histogram-kmeans",
            "version": "0.1",
            "configuration": {
                "histogramBins": config.histogram_bins,
                "maxKmeansIterations": config.max_kmeans_iterations,
                "convergenceTolerance": config.convergence_tolerance,
                "smoothingIterations": config.smoothing_iterations,
                "edgePercentile": config.edge_percentile,
                "minLayerFraction": config.min_layer_fraction,
            },
            "result": {
                "centersFarToNear": list(result.centers),
                "thresholdsFarToNear": list(result.thresholds),
                "fractionsFarToNear": list(result.fractions),
                "iterations": result.iterations,
            },
        },
        "coordinateSystem": {
            "origin": "top-left",
            "xAxis": "right",
            "yAxis": "down",
            "arrayOrder": "row-major (height, width)",
        },
        "artifacts": artifact_descriptions,
        "performance": {"layerBuildSeconds": elapsed_seconds},
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
