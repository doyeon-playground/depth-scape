"""Validation and loading for a completed relative-depth run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .contracts import IngestedImage

MAX_MANIFEST_BYTES = 1024 * 1024
MAX_NPY_HEADER_ALLOWANCE = 1024 * 1024


class DepthRunError(ValueError):
    """Raised when a prior depth run is missing, unsafe, or misaligned."""


@dataclass(frozen=True)
class LoadedDepthRun:
    """A validated, pixel-aligned relative-depth artifact and its identity."""

    depth: np.ndarray
    depth_sha256: str
    manifest_sha256: str
    model_id: str
    model_revision: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise DepthRunError(f"Depth manifest field {field} must be an object")
    return value


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise DepthRunError(f"Depth manifest field {field} must be a non-empty string")
    return value


def load_depth_run(run_dir: Path, *, image: IngestedImage) -> LoadedDepthRun:
    """Load a depth artifact only when its manifest matches the normalized image."""

    directory = run_dir.expanduser().resolve()
    if not directory.is_dir():
        raise DepthRunError(f"Depth run directory does not exist: {directory}")

    manifest_path = directory / "run.json"
    if not manifest_path.is_file():
        raise DepthRunError(f"Depth manifest does not exist: {manifest_path}")
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise DepthRunError(f"Depth manifest exceeds {MAX_MANIFEST_BYTES} bytes")

    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DepthRunError(f"Could not read depth manifest: {manifest_path}") from error
    root = _object(manifest, field="root")
    if root.get("schemaVersion") != "0.1":
        raise DepthRunError("Unsupported depth manifest schemaVersion")

    source = _object(root.get("source"), field="source")
    source_sha256 = _text(source.get("sha256"), field="source.sha256")
    if source_sha256 != image.source_sha256:
        raise DepthRunError("Depth run source hash does not match the input image")
    dimensions = _object(
        source.get("normalizedDimensions"),
        field="source.normalizedDimensions",
    )
    if dimensions.get("width") != image.width or dimensions.get("height") != image.height:
        raise DepthRunError("Depth run dimensions do not match the normalized input image")

    artifacts = _object(root.get("artifacts"), field="artifacts")
    relative_depth = _object(
        artifacts.get("relativeDepth"),
        field="artifacts.relativeDepth",
    )
    relative_path = Path(_text(relative_depth.get("path"), field="relativeDepth.path"))
    if relative_path.is_absolute():
        raise DepthRunError("Depth artifact path must be relative to its run directory")
    depth_path = (directory / relative_path).resolve()
    try:
        depth_path.relative_to(directory)
    except ValueError as error:
        raise DepthRunError("Depth artifact path escapes its run directory") from error
    if not depth_path.is_file():
        raise DepthRunError(f"Depth artifact does not exist: {depth_path}")

    expected_bytes = image.width * image.height * np.dtype(np.float32).itemsize
    if depth_path.stat().st_size > expected_bytes + MAX_NPY_HEADER_ALLOWANCE:
        raise DepthRunError("Depth artifact is larger than its declared dimensions allow")
    try:
        mapped = np.load(depth_path, allow_pickle=False, mmap_mode="r")
    except (OSError, ValueError) as error:
        raise DepthRunError(f"Could not load depth artifact: {depth_path}") from error
    if not isinstance(mapped, np.ndarray):
        if hasattr(mapped, "close"):
            mapped.close()
        raise DepthRunError("Depth artifact must be a single NumPy NPY array")
    if mapped.shape != (image.height, image.width):
        raise DepthRunError(
            f"Depth artifact shape {mapped.shape} does not match {(image.height, image.width)}"
        )
    if mapped.dtype != np.float32:
        raise DepthRunError(f"Depth artifact must be float32, got {mapped.dtype}")
    depth = np.asarray(mapped).copy()
    if not np.isfinite(depth).all() or depth.min() < 0.0 or depth.max() > 1.0:
        raise DepthRunError("Depth artifact must contain finite values in [0, 1]")

    model = _object(root.get("model"), field="model")
    return LoadedDepthRun(
        depth=depth,
        depth_sha256=_sha256(depth_path),
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        model_id=_text(model.get("id"), field="model.id"),
        model_revision=_text(model.get("revision"), field="model.revision"),
    )
