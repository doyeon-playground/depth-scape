"""Command-line entry point for the continuous relative-depth mesh experiment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .depth_run import DepthRunError
from .image_io import DEFAULT_MAX_FILE_BYTES, DEFAULT_MAX_PIXELS, ImageValidationError
from .mesh import MeshBuildConfig, MeshContractError
from .mesh_artifacts import MeshArtifactError
from .mesh_baseline import run_mesh_baseline


def build_parser() -> argparse.ArgumentParser:
    defaults = MeshBuildConfig()
    parser = argparse.ArgumentParser(
        description="Build a continuous relative-depth mesh with depth-edge cuts."
    )
    parser.add_argument("input", type=Path, help="The same local JPG or PNG used for depth")
    parser.add_argument(
        "--depth-run-dir",
        type=Path,
        required=True,
        help="Directory containing relative-depth.npy and run.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--max-mesh-dimension",
        type=int,
        default=defaults.max_mesh_dimension,
        help="Maximum sampled mesh rows or columns before preserving the final border",
    )
    parser.add_argument(
        "--depth-jump-threshold",
        type=float,
        default=defaults.depth_jump_threshold,
        help="Adjacent normalized-depth change that cuts intersecting mesh cells",
    )
    parser.add_argument(
        "--preview-overlay-alpha",
        type=float,
        default=defaults.preview_overlay_alpha,
        help="Opacity of red cut regions in the RGB-preserving diagnostic",
    )
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
        help="Replace only known continuous-mesh artifacts in the output directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_file_mib <= 0 or args.max_megapixels <= 0:
        parser.error("resource limits must be positive")

    config = MeshBuildConfig(
        max_mesh_dimension=args.max_mesh_dimension,
        depth_jump_threshold=args.depth_jump_threshold,
        preview_overlay_alpha=args.preview_overlay_alpha,
    )
    try:
        artifacts = run_mesh_baseline(
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
        MeshArtifactError,
        MeshContractError,
    ) as error:
        print(f"depth-scape-mesh: error: {error}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "texture": str(artifacts.texture),
                "vertices": str(artifacts.vertices),
                "faces": str(artifacts.faces),
                "preview": str(artifacts.preview),
                "manifest": str(artifacts.manifest),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
