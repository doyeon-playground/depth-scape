"""Command-line entry point for the DepthScape depth baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters.depth_anything_v2 import (
    DepthAnythingV2Estimator,
    DepthAnythingV2Settings,
    DepthBackendError,
)
from .artifacts import ArtifactWriteError
from .baseline import run_depth_baseline
from .depth import DepthContractError
from .image_io import DEFAULT_MAX_FILE_BYTES, DEFAULT_MAX_PIXELS, ImageValidationError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a relative-depth artifact from one local JPG or PNG."
    )
    parser.add_argument("input", type=Path, help="Path to a local JPG or PNG")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for relative-depth.npy, depth-preview.png, and run.json",
    )
    parser.add_argument("--device", default="auto", help="auto, cpu, mps, cuda, or cuda:N")
    parser.add_argument(
        "--precision",
        choices=("auto", "float32", "float16", "bfloat16"),
        default="auto",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--max-file-mib",
        type=float,
        default=DEFAULT_MAX_FILE_BYTES / (1024 * 1024),
    )
    parser.add_argument(
        "--max-megapixels",
        type=float,
        default=DEFAULT_MAX_PIXELS / 1_000_000,
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use only model files already present in the Hugging Face cache",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace only the three known artifacts in the output directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_file_mib <= 0 or args.max_megapixels <= 0:
        parser.error("resource limits must be positive")

    estimator = DepthAnythingV2Estimator(
        DepthAnythingV2Settings(
            device=args.device,
            precision=args.precision,
            offline=args.offline,
        )
    )
    try:
        artifacts = run_depth_baseline(
            input_path=args.input,
            output_dir=args.output_dir,
            estimator=estimator,
            seed=args.seed,
            max_file_bytes=int(args.max_file_mib * 1024 * 1024),
            max_pixels=int(args.max_megapixels * 1_000_000),
            overwrite=args.overwrite,
        )
    except (
        ArtifactWriteError,
        DepthBackendError,
        DepthContractError,
        ImageValidationError,
    ) as error:
        print(f"depth-scape-depth: error: {error}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "depth": str(artifacts.depth),
                "preview": str(artifacts.preview),
                "manifest": str(artifacts.manifest),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
