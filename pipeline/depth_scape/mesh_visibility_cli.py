"""Command-line entry point for bounded continuous-mesh camera evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .mesh_renderer import MeshRenderError
from .mesh_run import MeshRunError
from .mesh_visibility import MeshVisibilityConfig, MeshVisibilityError
from .mesh_visibility_artifacts import MeshVisibilityArtifactError
from .mesh_visibility_baseline import run_mesh_visibility_baseline


def build_parser() -> argparse.ArgumentParser:
    defaults = MeshVisibilityConfig()
    parser = argparse.ArgumentParser(
        description="Render a bounded continuous-mesh camera path and measure holes."
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
        default=defaults.max_render_dimension,
        help="Maximum output width or height for the CPU visibility experiment",
    )
    parser.add_argument(
        "--max-faces",
        type=int,
        default=defaults.max_faces,
        help="Maximum triangle count accepted by the CPU visibility experiment",
    )
    parser.add_argument(
        "--max-near-shift-fraction",
        type=float,
        default=defaults.max_near_shift_fraction,
        help="Maximum endpoint displacement of nearest content as a viewport-width fraction",
    )
    parser.add_argument(
        "--max-near-shift-pixels",
        type=int,
        default=defaults.max_near_shift_pixels,
        help="Pixel cap for endpoint displacement of nearest content",
    )
    parser.add_argument(
        "--sampled-positions",
        type=int,
        default=defaults.sampled_positions,
        help=(
            "Optional odd camera-position count; by default it is derived from the "
            "maximum sample shift step"
        ),
    )
    parser.add_argument(
        "--max-sample-shift-step-pixels",
        type=int,
        default=defaults.max_sample_shift_step_pixels,
        help="Maximum nearest-surface pixel displacement between automatic samples",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace only known mesh-camera artifacts in the output directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = MeshVisibilityConfig(
        max_render_dimension=args.max_render_dimension,
        max_faces=args.max_faces,
        max_near_shift_fraction=args.max_near_shift_fraction,
        max_near_shift_pixels=args.max_near_shift_pixels,
        sampled_positions=args.sampled_positions,
        max_sample_shift_step_pixels=args.max_sample_shift_step_pixels,
    )
    try:
        artifacts = run_mesh_visibility_baseline(
            mesh_run_dir=args.mesh_run_dir,
            output_dir=args.output_dir,
            config=config,
            overwrite=args.overwrite,
        )
    except (
        MeshRenderError,
        MeshRunError,
        MeshVisibilityArtifactError,
        MeshVisibilityError,
    ) as error:
        print(f"depth-scape-render: error: {error}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "centerView": str(artifacts.center_view),
                "leftView": str(artifacts.left_view),
                "rightView": str(artifacts.right_view),
                "allViewHoles": str(artifacts.all_view_holes),
                "manifest": str(artifacts.manifest),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
