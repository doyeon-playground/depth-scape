"""Validation and loading for a completed three-layer run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MAX_MANIFEST_BYTES = 1024 * 1024
MAX_NPY_HEADER_ALLOWANCE = 1024 * 1024


class LayerRunError(ValueError):
    """Raised when a prior layer run is missing, unsafe, or inconsistent."""


@dataclass(frozen=True)
class LoadedLayerRun:
    """A validated three-layer label map and its reproducibility identity."""

    labels: np.ndarray
    width: int
    height: int
    source_sha256: str
    layer_map_sha256: str
    manifest_sha256: str
    algorithm_id: str
    algorithm_version: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise LayerRunError(f"Layer manifest field {field} must be an object")
    return value


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise LayerRunError(f"Layer manifest field {field} must be a non-empty string")
    return value


def _positive_integer(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise LayerRunError(f"Layer manifest field {field} must be a positive integer")
    return value


def load_layer_run(run_dir: Path) -> LoadedLayerRun:
    """Load a three-layer map only when its compact manifest is self-consistent."""

    directory = run_dir.expanduser().resolve()
    if not directory.is_dir():
        raise LayerRunError(f"Layer run directory does not exist: {directory}")

    manifest_path = directory / "layers.json"
    if not manifest_path.is_file():
        raise LayerRunError(f"Layer manifest does not exist: {manifest_path}")
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise LayerRunError(f"Layer manifest exceeds {MAX_MANIFEST_BYTES} bytes")

    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LayerRunError(f"Could not read layer manifest: {manifest_path}") from error
    root = _object(manifest, field="root")
    if root.get("schemaVersion") != "0.1":
        raise LayerRunError("Unsupported layer manifest schemaVersion")

    source = _object(root.get("source"), field="source")
    source_sha256 = _text(source.get("sha256"), field="source.sha256")
    dimensions = _object(source.get("dimensions"), field="source.dimensions")
    width = _positive_integer(dimensions.get("width"), field="source.dimensions.width")
    height = _positive_integer(dimensions.get("height"), field="source.dimensions.height")

    artifacts = _object(root.get("artifacts"), field="artifacts")
    layer_map = _object(artifacts.get("layerMap"), field="artifacts.layerMap")
    relative_path = Path(_text(layer_map.get("path"), field="layerMap.path"))
    if relative_path.is_absolute():
        raise LayerRunError("Layer-map path must be relative to its run directory")
    layer_map_path = (directory / relative_path).resolve()
    try:
        layer_map_path.relative_to(directory)
    except ValueError as error:
        raise LayerRunError("Layer-map path escapes its run directory") from error
    if not layer_map_path.is_file():
        raise LayerRunError(f"Layer-map artifact does not exist: {layer_map_path}")

    expected_bytes = width * height * np.dtype(np.uint8).itemsize
    if layer_map_path.stat().st_size > expected_bytes + MAX_NPY_HEADER_ALLOWANCE:
        raise LayerRunError("Layer-map artifact is larger than its dimensions allow")
    try:
        mapped = np.load(layer_map_path, allow_pickle=False, mmap_mode="r")
    except (OSError, ValueError) as error:
        raise LayerRunError(f"Could not load layer-map artifact: {layer_map_path}") from error
    if not isinstance(mapped, np.ndarray):
        if hasattr(mapped, "close"):
            mapped.close()
        raise LayerRunError("Layer-map artifact must be a single NumPy NPY array")
    if mapped.shape != (height, width):
        raise LayerRunError(f"Layer-map shape {mapped.shape} does not match {(height, width)}")
    if mapped.dtype != np.uint8:
        raise LayerRunError(f"Layer-map artifact must be uint8, got {mapped.dtype}")
    labels = np.asarray(mapped).copy()
    if set(int(value) for value in np.unique(labels)) != {0, 1, 2}:
        raise LayerRunError("Layer-map artifact must contain all labels 0, 1, and 2 only")

    actual_sha256 = _sha256(layer_map_path)
    declared_sha256 = _text(layer_map.get("sha256"), field="layerMap.sha256")
    if declared_sha256 != actual_sha256:
        raise LayerRunError("Layer-map SHA-256 does not match its manifest")

    algorithm = _object(root.get("algorithm"), field="algorithm")
    return LoadedLayerRun(
        labels=np.ascontiguousarray(labels),
        width=width,
        height=height,
        source_sha256=source_sha256,
        layer_map_sha256=actual_sha256,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        algorithm_id=_text(algorithm.get("id"), field="algorithm.id"),
        algorithm_version=_text(algorithm.get("version"), field="algorithm.version"),
    )
