"""Command-line entry point for hidden-surface request planning."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .hidden_surface import HiddenSurfaceConfig, HiddenSurfaceContractError
from .hidden_surface_artifacts import HiddenSurfaceArtifactError
from .hidden_surface_baseline import run_hidden_surface_baseline
from .mesh_renderer import MeshRenderError
from .mesh_run import MeshRunError
from .mesh_visibility import MeshVisibilityConfig, MeshVisibilityError


def build_parser() -> argparse.ArgumentParser:
    visibility_defaults = MeshVisibilityConfig()
    hidden_defaults = HiddenSurfaceConfig()
    parser = argparse.ArgumentParser(
        description=(
            "Map bounded mesh-view holes to a coupled hidden RGB and relative-depth request."
        )
    )
    parser.add_argument(
        "--mesh-run-dir",
        type=Path,
        required=True,
        help="Directory containing observed texture, mesh arrays, and mesh.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--max-render-dimension",
        type=int,
        default=visibility_defaults.max_render_dimension,
    )
    parser.add_argument(
        "--max-faces",
        type=int,
        default=visibility_defaults.max_faces,
    )
    parser.add_argument(
        "--max-near-shift-fraction",
        type=float,
        default=visibility_defaults.max_near_shift_fraction,
    )
    parser.add_argument(
        "--max-near-shift-pixels",
        type=int,
        default=visibility_defaults.max_near_shift_pixels,
    )
    parser.add_argument(
        "--sampled-positions",
        type=int,
        default=visibility_defaults.sampled_positions,
    )
    parser.add_argument(
        "--min-depth-separation",
        type=float,
        default=hidden_defaults.min_depth_separation,
        help="Minimum near-minus-far relative-depth gap for a safe mapping",
    )
    parser.add_argument(
        "--max-request-pixels",
        type=int,
        default=hidden_defaults.max_request_pixels,
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace only known hidden-surface artifacts in the output directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    visibility_config = MeshVisibilityConfig(
        max_render_dimension=args.max_render_dimension,
        max_faces=args.max_faces,
        max_near_shift_fraction=args.max_near_shift_fraction,
        max_near_shift_pixels=args.max_near_shift_pixels,
        sampled_positions=args.sampled_positions,
    )
    hidden_surface_config = HiddenSurfaceConfig(
        min_depth_separation=args.min_depth_separation,
        max_request_pixels=args.max_request_pixels,
    )
    try:
        artifacts = run_hidden_surface_baseline(
            mesh_run_dir=args.mesh_run_dir,
            output_dir=args.output_dir,
            visibility_config=visibility_config,
            hidden_surface_config=hidden_surface_config,
            overwrite=args.overwrite,
        )
    except (
        HiddenSurfaceArtifactError,
        HiddenSurfaceContractError,
        MeshRenderError,
        MeshRunError,
        MeshVisibilityError,
    ) as error:
        print(f"depth-scape-hidden: error: {error}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "requestMask": str(artifacts.request_mask),
                "relativeDepthHint": str(artifacts.relative_depth_hint),
                "outpaintRequestMask": str(artifacts.outpaint_request_mask),
                "unresolvedViewHoles": str(artifacts.unresolved_view_holes),
                "preview": str(artifacts.completion_preview),
                "manifest": str(artifacts.manifest),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
