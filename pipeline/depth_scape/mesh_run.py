"""Validation and loading for a completed continuous-mesh run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from .image_io import DEFAULT_MAX_PIXELS

MAX_MANIFEST_BYTES = 1024 * 1024
MAX_ARTIFACT_BYTES = 256 * 1024 * 1024


class MeshRunError(ValueError):
    """Raised when a prior mesh run is missing, unsafe, or inconsistent."""


@dataclass(frozen=True)
class LoadedMeshRun:
    """Validated observed texture and inferred continuous-mesh arrays.

    ``texture`` is uint8 ``HxWx3`` observed RGB. ``vertices`` is float32
    ``Nx3`` in the aspect-correct mesh coordinate system, ``texture_coordinates``
    is float32 ``Nx2`` with a top-left origin, and ``faces`` is int32 ``Mx3``.
    """

    texture: np.ndarray
    vertices: np.ndarray
    texture_coordinates: np.ndarray
    faces: np.ndarray
    source_sha256: str
    manifest_sha256: str
    manifest_path: Path
    algorithm_id: str
    algorithm_version: str

    @property
    def width(self) -> int:
        return int(self.texture.shape[1])

    @property
    def height(self) -> int:
        return int(self.texture.shape[0])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MeshRunError(f"Mesh manifest field {field} must be an object")
    return value


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise MeshRunError(f"Mesh manifest field {field} must be a non-empty string")
    return value


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise MeshRunError(f"Mesh manifest field {field} must be a positive integer")
    return value


def _artifact_path(
    directory: Path,
    artifacts: dict[str, object],
    *,
    key: str,
) -> tuple[Path, dict[str, object]]:
    description = _object(artifacts.get(key), field=f"artifacts.{key}")
    relative = Path(_text(description.get("path"), field=f"artifacts.{key}.path"))
    if relative.is_absolute():
        raise MeshRunError(f"Mesh artifact {key} path must be relative")
    path = (directory / relative).resolve()
    try:
        path.relative_to(directory)
    except ValueError as error:
        raise MeshRunError(f"Mesh artifact {key} path escapes its run directory") from error
    if not path.is_file():
        raise MeshRunError(f"Mesh artifact {key} does not exist: {path}")
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise MeshRunError(f"Mesh artifact {key} exceeds {MAX_ARTIFACT_BYTES} bytes")
    expected_hash = _text(description.get("sha256"), field=f"artifacts.{key}.sha256")
    if _sha256(path) != expected_hash:
        raise MeshRunError(f"Mesh artifact {key} hash does not match its manifest")
    return path, description


def _load_array(
    path: Path,
    *,
    key: str,
    dtype: np.dtype[object],
    columns: int,
) -> np.ndarray:
    try:
        mapped = np.load(path, allow_pickle=False, mmap_mode="r")
    except (OSError, ValueError) as error:
        raise MeshRunError(f"Could not load mesh artifact {key}: {path}") from error
    if not isinstance(mapped, np.ndarray):
        if hasattr(mapped, "close"):
            mapped.close()
        raise MeshRunError(f"Mesh artifact {key} must be a single NumPy NPY array")
    if mapped.ndim != 2 or mapped.shape[1] != columns:
        raise MeshRunError(f"Mesh artifact {key} must have shape Nx{columns}, got {mapped.shape}")
    if mapped.dtype != dtype:
        raise MeshRunError(f"Mesh artifact {key} must be {dtype}, got {mapped.dtype}")
    values = np.asarray(mapped).copy()
    return np.ascontiguousarray(values)


def load_mesh_run(run_dir: Path) -> LoadedMeshRun:
    """Load a mesh run only after validating its paths, hashes, and array contracts."""

    directory = run_dir.expanduser().resolve()
    if not directory.is_dir():
        raise MeshRunError(f"Mesh run directory does not exist: {directory}")
    manifest_path = directory / "mesh.json"
    if not manifest_path.is_file():
        raise MeshRunError(f"Mesh manifest does not exist: {manifest_path}")
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise MeshRunError(f"Mesh manifest exceeds {MAX_MANIFEST_BYTES} bytes")

    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MeshRunError(f"Could not read mesh manifest: {manifest_path}") from error
    root = _object(manifest, field="root")
    if root.get("schemaVersion") != "0.1":
        raise MeshRunError("Unsupported mesh manifest schemaVersion")

    source = _object(root.get("source"), field="source")
    dimensions = _object(source.get("dimensions"), field="source.dimensions")
    width = _positive_int(dimensions.get("width"), field="source.dimensions.width")
    height = _positive_int(dimensions.get("height"), field="source.dimensions.height")
    if width < 2 or height < 2:
        raise MeshRunError("Mesh source dimensions must both be at least 2 pixels")
    if width * height > DEFAULT_MAX_PIXELS:
        raise MeshRunError(f"Mesh observed texture exceeds {DEFAULT_MAX_PIXELS} pixels")
    source_sha256 = _text(source.get("sha256"), field="source.sha256")

    artifacts = _object(root.get("artifacts"), field="artifacts")
    texture_path, _ = _artifact_path(directory, artifacts, key="observedTexture")
    vertices_path, _ = _artifact_path(directory, artifacts, key="vertices")
    uv_path, _ = _artifact_path(directory, artifacts, key="textureCoordinates")
    faces_path, _ = _artifact_path(directory, artifacts, key="faces")

    try:
        with Image.open(texture_path) as opened:
            if opened.format != "PNG" or opened.mode != "RGB":
                raise MeshRunError("Observed mesh texture must be an RGB PNG")
            if opened.size != (width, height):
                raise MeshRunError("Observed mesh texture dimensions do not match the manifest")
            texture = np.asarray(opened).copy()
    except (OSError, UnidentifiedImageError) as error:
        raise MeshRunError(f"Could not load observed mesh texture: {texture_path}") from error

    vertices = _load_array(
        vertices_path,
        key="vertices",
        dtype=np.dtype(np.float32),
        columns=3,
    )
    texture_coordinates = _load_array(
        uv_path,
        key="textureCoordinates",
        dtype=np.dtype(np.float32),
        columns=2,
    )
    faces = _load_array(
        faces_path,
        key="faces",
        dtype=np.dtype(np.int32),
        columns=3,
    )
    if vertices.shape[0] < 3 or faces.shape[0] < 1:
        raise MeshRunError("Mesh run must contain at least three vertices and one face")
    if texture_coordinates.shape[0] != vertices.shape[0]:
        raise MeshRunError("Mesh texture-coordinate count does not match vertex count")
    if not np.isfinite(vertices).all():
        raise MeshRunError("Mesh vertices must contain only finite values")
    if (
        not np.isfinite(texture_coordinates).all()
        or texture_coordinates.min() < 0.0
        or texture_coordinates.max() > 1.0
    ):
        raise MeshRunError("Mesh texture coordinates must be finite and in [0, 1]")
    if faces.min() < 0 or faces.max() >= vertices.shape[0]:
        raise MeshRunError("Mesh faces contain an out-of-range vertex index")
    if np.any(
        (faces[:, 0] == faces[:, 1]) | (faces[:, 1] == faces[:, 2]) | (faces[:, 0] == faces[:, 2])
    ):
        raise MeshRunError("Mesh faces must reference three distinct vertices")

    algorithm = _object(root.get("algorithm"), field="algorithm")
    return LoadedMeshRun(
        texture=np.ascontiguousarray(texture, dtype=np.uint8),
        vertices=vertices,
        texture_coordinates=texture_coordinates,
        faces=faces,
        source_sha256=source_sha256,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        manifest_path=manifest_path,
        algorithm_id=_text(algorithm.get("id"), field="algorithm.id"),
        algorithm_version=_text(algorithm.get("version"), field="algorithm.version"),
    )
