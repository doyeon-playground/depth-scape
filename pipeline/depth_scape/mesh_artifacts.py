"""Artifact writer for the continuous relative-depth mesh experiment."""

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
from .mesh import MeshBuildConfig, MeshBuildResult, mesh_preview

MESH_MANIFEST_FILENAME = "mesh.json"


class MeshArtifactError(RuntimeError):
    """Raised when mesh output would overwrite or target unsafe paths."""


@dataclass(frozen=True)
class MeshArtifacts:
    """Paths created by a completed continuous-depth mesh run."""

    texture: Path
    vertices: Path
    texture_coordinates: Path
    faces: Path
    sample_x: Path
    sample_y: Path
    cut_cells: Path
    preview: Path
    manifest: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pixel_sha256(values: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()


def _prepare_targets(output_dir: Path, *, overwrite: bool) -> MeshArtifacts:
    directory = output_dir.expanduser().resolve()
    if directory.exists() and not directory.is_dir():
        raise MeshArtifactError(f"Output path is not a directory: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    artifacts = MeshArtifacts(
        texture=directory / "observed-texture.png",
        vertices=directory / "mesh-vertices.npy",
        texture_coordinates=directory / "mesh-uv.npy",
        faces=directory / "mesh-faces.npy",
        sample_x=directory / "mesh-sample-x.npy",
        sample_y=directory / "mesh-sample-y.npy",
        cut_cells=directory / "mesh-cut-cells.png",
        preview=directory / "mesh-preview.png",
        manifest=directory / MESH_MANIFEST_FILENAME,
    )
    existing = [path for path in artifacts.__dict__.values() if path.exists()]
    if existing and not overwrite:
        names = ", ".join(path.name for path in existing)
        raise MeshArtifactError(
            f"Refusing to overwrite existing mesh artifacts ({names}); pass --overwrite"
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


def _array_artifact(
    path: Path,
    values: np.ndarray,
    *,
    meaning: str,
    provenance: str,
) -> dict[str, object]:
    return {
        "path": path.name,
        "format": "NumPy NPY",
        "dtype": str(values.dtype),
        "shape": [int(value) for value in values.shape],
        "meaning": meaning,
        "provenance": provenance,
        "sha256": _sha256(path),
    }


def write_mesh_artifacts(
    *,
    output_dir: Path,
    image: IngestedImage,
    depth_run: LoadedDepthRun,
    result: MeshBuildResult,
    config: MeshBuildConfig,
    elapsed_seconds: float,
    overwrite: bool,
) -> MeshArtifacts:
    """Write observed texture, mesh arrays, diagnostics, and metadata."""

    artifacts = _prepare_targets(output_dir, overwrite=overwrite)
    source_rgb = np.asarray(image.image, dtype=np.uint8)
    cut_cells = np.where(result.cut_cells, 255, 0).astype(np.uint8)
    preview = mesh_preview(
        image.image,
        result.cut_source_mask,
        overlay_alpha=config.preview_overlay_alpha,
    )
    _write_png(artifacts.texture, source_rgb)
    _write_npy(artifacts.vertices, result.vertices)
    _write_npy(artifacts.texture_coordinates, result.texture_coordinates)
    _write_npy(artifacts.faces, result.faces)
    _write_npy(artifacts.sample_x, result.sample_x)
    _write_npy(artifacts.sample_y, result.sample_y)
    _write_png(artifacts.cut_cells, cut_cells)
    _write_png(artifacts.preview, preview)

    with Image.open(artifacts.texture) as opened:
        texture_pixels = np.asarray(opened.convert("RGB")).copy()
    if not np.array_equal(texture_pixels, source_rgb):
        raise MeshArtifactError("Observed texture does not preserve normalized source pixels")

    git_revision, git_dirty = git_state()
    warnings = [
        "Mesh Z values are unitless relative proximity, not metric distance.",
        "Removed faces mark inferred depth discontinuities; they are not deleted source pixels.",
        "The mesh does not contain hidden geometry or generated RGB.",
        "A renderer must stay inside separately verified camera bounds.",
    ]
    if git_dirty:
        warnings.append("DepthScape source checkout had uncommitted changes during this run.")

    artifact_descriptions: dict[str, object] = {
        "observedTexture": {
            "path": artifacts.texture.name,
            "format": "PNG",
            "dtype": "uint8",
            "shape": [image.height, image.width, 3],
            "colorSpace": image.color_space,
            "meaning": "normalized source RGB used as the mesh texture",
            "provenance": "observed",
            "pixelSha256": _pixel_sha256(texture_pixels),
            "sha256": _sha256(artifacts.texture),
        },
        "vertices": _array_artifact(
            artifacts.vertices,
            result.vertices,
            meaning="aspect-correct X/Y coordinates and relative-proximity Z",
            provenance="derived from observed coordinates and inferred depth",
        ),
        "textureCoordinates": _array_artifact(
            artifacts.texture_coordinates,
            result.texture_coordinates,
            meaning="top-left-origin normalized texture coordinates",
            provenance="derived from observed pixel coordinates",
        ),
        "faces": _array_artifact(
            artifacts.faces,
            result.faces,
            meaning="triangles retained after depth-discontinuity cuts",
            provenance="inferred geometry",
        ),
        "sampleX": _array_artifact(
            artifacts.sample_x,
            result.sample_x,
            meaning="source-image X coordinates sampled by mesh columns",
            provenance="derived from observed pixel coordinates",
        ),
        "sampleY": _array_artifact(
            artifacts.sample_y,
            result.sample_y,
            meaning="source-image Y coordinates sampled by mesh rows",
            provenance="derived from observed pixel coordinates",
        ),
        "cutCells": {
            "path": artifacts.cut_cells.name,
            "format": "PNG",
            "dtype": "uint8",
            "shape": [int(result.cut_cells.shape[0]), int(result.cut_cells.shape[1])],
            "meaning": "255=cell triangles omitted, 0=cell triangles retained",
            "coordinateSpace": "mesh cell grid",
            "provenance": "inferred from relative-depth discontinuities",
            "sha256": _sha256(artifacts.cut_cells),
        },
        "preview": {
            "path": artifacts.preview.name,
            "format": "PNG",
            "meaning": "observed RGB with cut-cell source footprints overlaid in red",
            "provenance": "display-only diagnostic derived from observed and inferred data",
            "sha256": _sha256(artifacts.preview),
        },
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
            "id": "continuous-depth-grid-cut",
            "version": "0.1",
            "configuration": {
                "maxMeshDimension": config.max_mesh_dimension,
                "depthJumpThreshold": config.depth_jump_threshold,
                "previewOverlayAlpha": config.preview_overlay_alpha,
            },
            "result": {
                "samplingStridePixels": result.sampling_stride,
                "gridDimensions": {
                    "width": int(result.sample_x.size),
                    "height": int(result.sample_y.size),
                },
                "vertexCount": int(result.vertices.shape[0]),
                "faceCount": int(result.faces.shape[0]),
                "cutCellCount": int(np.count_nonzero(result.cut_cells)),
                "cutCellFraction": float(np.mean(result.cut_cells)),
                "retainedFaceFraction": result.retained_face_fraction,
                "defaultTexturePixelIdentical": True,
            },
        },
        "coordinateSystem": {
            "mesh": {
                "handedness": "right-handed",
                "xAxis": "right",
                "yAxis": "up",
                "zAxis": "toward viewer; larger relative proximity is nearer",
                "xRange": [-image.width / image.height, image.width / image.height],
                "yRange": [-1.0, 1.0],
                "zRange": [0.0, 1.0],
                "faceWinding": "counter-clockwise when viewed from positive Z",
            },
            "texture": {
                "origin": "top-left",
                "uAxis": "right",
                "vAxis": "down",
                "range": [0.0, 1.0],
            },
        },
        "artifacts": artifact_descriptions,
        "performance": {"meshBuildSeconds": elapsed_seconds},
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
