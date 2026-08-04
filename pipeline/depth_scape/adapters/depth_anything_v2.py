"""Lazy Transformers adapter for the pinned Depth Anything V2 Small baseline."""

from __future__ import annotations

import importlib.metadata
import time
from dataclasses import dataclass

import numpy as np
from PIL import Image

from ..contracts import DepthPrediction, InferenceTelemetry, ModelIdentity

MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
MODEL_REVISION = "5426e4f0f36572d16453bbda7a8389317b1bef99"
MODEL_UPSTREAM_CODE_LICENSE = "Apache-2.0"
MODEL_WEIGHTS_LICENSE = "Apache-2.0"
BACKEND_CODE_LICENSE = "Apache-2.0"
MODEL_WEIGHTS_SHA256 = "3152477ce0d8d6978d76b995120de97cb5b928701fd0f817769f59e249a16b70"
MODEL_WEIGHTS_BYTES = 99_173_660
MODEL_SOURCE_URL = f"https://huggingface.co/{MODEL_ID}"


class DepthBackendError(RuntimeError):
    """Raised when the optional model backend is unavailable or incompatible."""


@dataclass(frozen=True)
class DepthAnythingV2Settings:
    """Runtime-only settings for the pinned baseline adapter."""

    device: str = "auto"
    precision: str = "auto"
    offline: bool = False


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


class DepthAnythingV2Estimator:
    """Infer unitless relative proximity with Depth Anything V2 Small.

    Model imports and downloads occur only when ``predict`` is called. The
    immutable model revision and weight digest are part of every output manifest.
    """

    def __init__(self, settings: DepthAnythingV2Settings | None = None) -> None:
        self.settings = settings or DepthAnythingV2Settings()

    def _runtime(self):
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        except ImportError as error:
            raise DepthBackendError(
                'Depth dependencies are missing; install with pip install -e ".[depth]"'
            ) from error
        return torch, AutoImageProcessor, AutoModelForDepthEstimation

    def _resolve_device(self, torch):
        requested = self.settings.device
        if requested == "auto":
            if torch.cuda.is_available():
                requested = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                requested = "mps"
            else:
                requested = "cpu"

        device = torch.device(requested)
        if device.type == "cuda" and not torch.cuda.is_available():
            raise DepthBackendError("CUDA was requested but is not available")
        if device.type == "mps" and not (
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        ):
            raise DepthBackendError("MPS was requested but is not available")
        return device

    def _resolve_dtype(self, torch, device):
        precision = self.settings.precision
        if precision == "auto":
            precision = "float16" if device.type == "cuda" else "float32"
        dtypes = {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }
        if precision not in dtypes:
            raise DepthBackendError(
                f"Unsupported precision {precision!r}; use auto, float32, float16, or bfloat16"
            )
        if device.type != "cuda" and precision != "float32":
            raise DepthBackendError(
                f"Precision {precision} is not supported by this baseline on {device.type}"
            )
        return precision, dtypes[precision]

    def predict(self, image: Image.Image, *, seed: int) -> DepthPrediction:
        """Return an HxW float32 map where larger values indicate nearer content."""

        if image.mode != "RGB":
            raise DepthBackendError(f"Expected an RGB image, got {image.mode}")

        torch, processor_type, model_type = self._runtime()
        device = self._resolve_device(torch)
        precision, dtype = self._resolve_dtype(torch, device)

        torch.manual_seed(seed)
        if device.type == "cuda":
            torch.cuda.manual_seed_all(seed)
            torch.cuda.reset_peak_memory_stats(device)
        torch.use_deterministic_algorithms(True, warn_only=True)

        load_started = time.perf_counter()
        try:
            processor = processor_type.from_pretrained(
                MODEL_ID,
                revision=MODEL_REVISION,
                local_files_only=self.settings.offline,
                use_fast=False,
            )
            model = model_type.from_pretrained(
                MODEL_ID,
                revision=MODEL_REVISION,
                local_files_only=self.settings.offline,
                use_safetensors=True,
                dtype=dtype,
            )
        except (OSError, ValueError) as error:
            mode = "local cache" if self.settings.offline else "Hugging Face"
            raise DepthBackendError(
                f"Could not load pinned checkpoint {MODEL_ID}@{MODEL_REVISION} from {mode}"
            ) from error
        model = model.to(device).eval()
        model_load_seconds = time.perf_counter() - load_started

        if getattr(model.config, "depth_estimation_type", None) != "relative":
            raise DepthBackendError("Pinned checkpoint no longer reports relative depth")

        encoded = processor(images=image, return_tensors="pt")
        inputs = {
            name: tensor.to(
                device=device,
                dtype=dtype if torch.is_floating_point(tensor) else tensor.dtype,
            )
            for name, tensor in encoded.items()
        }

        if device.type == "cuda":
            torch.cuda.synchronize(device)
        inference_started = time.perf_counter()
        with torch.inference_mode():
            outputs = model(**inputs)
            processed = processor.post_process_depth_estimation(
                outputs,
                target_sizes=[(image.height, image.width)],
            )
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        inference_seconds = time.perf_counter() - inference_started

        predicted = processed[0]["predicted_depth"]
        values = predicted.detach().to(dtype=torch.float32).cpu().numpy()
        peak_memory = (
            int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else None
        )
        device_name = (
            torch.cuda.get_device_name(device) if device.type == "cuda" else device.type.upper()
        )
        warnings = ()
        if peak_memory is None:
            warnings = ("Peak memory is unavailable on this non-CUDA baseline path.",)

        return DepthPrediction(
            values=np.asarray(values, dtype=np.float32),
            model=ModelIdentity(
                model_id=MODEL_ID,
                revision=MODEL_REVISION,
                backend="transformers",
                upstream_code_license=MODEL_UPSTREAM_CODE_LICENSE,
                weights_license=MODEL_WEIGHTS_LICENSE,
                backend_code_license=BACKEND_CODE_LICENSE,
                weights_sha256=MODEL_WEIGHTS_SHA256,
                weights_bytes=MODEL_WEIGHTS_BYTES,
                source_url=MODEL_SOURCE_URL,
            ),
            telemetry=InferenceTelemetry(
                device=str(device),
                device_name=device_name,
                precision=precision,
                model_load_seconds=model_load_seconds,
                inference_seconds=inference_seconds,
                peak_accelerator_memory_bytes=peak_memory,
                package_versions={
                    "numpy": _package_version("numpy"),
                    "Pillow": _package_version("Pillow"),
                    "safetensors": _package_version("safetensors"),
                    "torch": _package_version("torch"),
                    "transformers": _package_version("transformers"),
                },
                warnings=warnings,
            ),
        )
