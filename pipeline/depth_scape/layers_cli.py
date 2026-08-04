"""Command-line entry point for the DepthScape three-layer baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .depth_run import DepthRunError
from .image_io import DEFAULT_MAX_FILE_BYTES, DEFAULT_MAX_PIXELS, ImageValidationError
from .layer_artifacts import LayerArtifactError
from .layer_baseline import run_layer_baseline
from .layers import LayerBuildConfig, LayerContractError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build inferred background, midground, and foreground masks."
    )
    parser.add_argument("input", type=Path, help="The same local JPG or PNG used for depth")
    parser.add_argument(
        "--depth-run-dir",
        type=Path,
        required=True,
        help="Directory containing relative-depth.npy and run.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--histogram-bins", type=int, default=4096)
    parser.add_argument("--max-kmeans-iterations", type=int, default=64)
    parser.add_argument("--convergence-tolerance", type=float, default=1e-6)
    parser.add_argument("--smoothing-iterations", type=int, default=2)
    parser.add_argument("--edge-percentile", type=float, default=90.0)
    parser.add_argument("--min-layer-fraction", type=float, default=0.01)
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
        "--overwrite",
        action="store_true",
        help="Replace only the known layer artifacts in the output directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_file_mib <= 0 or args.max_megapixels <= 0:
        parser.error("resource limits must be positive")

    config = LayerBuildConfig(
        histogram_bins=args.histogram_bins,
        max_kmeans_iterations=args.max_kmeans_iterations,
        convergence_tolerance=args.convergence_tolerance,
        smoothing_iterations=args.smoothing_iterations,
        edge_percentile=args.edge_percentile,
        min_layer_fraction=args.min_layer_fraction,
    )
    try:
        artifacts = run_layer_baseline(
            input_path=args.input,
            depth_run_dir=args.depth_run_dir,
            output_dir=args.output_dir,
            config=config,
            max_file_bytes=int(args.max_file_mib * 1024 * 1024),
            max_pixels=int(args.max_megapixels * 1_000_000),
            overwrite=args.overwrite,
        )
    except (
        DepthRunError,
        ImageValidationError,
        LayerArtifactError,
        LayerContractError,
    ) as error:
        print(f"depth-scape-layers: error: {error}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "layerMap": str(artifacts.layer_map),
                "preview": str(artifacts.preview),
                "manifest": str(artifacts.manifest),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
