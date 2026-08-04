"""Command-line entry point for DepthScape visibility planning."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .layer_run import LayerRunError
from .visibility import VisibilityConfig, VisibilityContractError
from .visibility_artifacts import VisibilityArtifactError
from .visibility_baseline import run_visibility_baseline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan bounded horizontal camera motion and disocclusion masks."
    )
    parser.add_argument(
        "--layer-run-dir",
        type=Path,
        required=True,
        help="Directory containing layer-map.npy and layers.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--max-shift-percent",
        type=float,
        default=2.0,
        help="Maximum foreground screen shift as a percentage of source width",
    )
    parser.add_argument(
        "--max-shift-pixels",
        type=int,
        default=64,
        help="Hard cap on the maximum foreground screen shift",
    )
    parser.add_argument(
        "--midground-factor",
        type=float,
        default=0.5,
        help="Midground screen shift relative to foreground",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace only known visibility artifacts in the output directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = VisibilityConfig(
        max_foreground_shift_fraction=args.max_shift_percent / 100.0,
        max_foreground_shift_pixels=args.max_shift_pixels,
        midground_parallax_factor=args.midground_factor,
    )
    try:
        artifacts = run_visibility_baseline(
            layer_run_dir=args.layer_run_dir,
            output_dir=args.output_dir,
            config=config,
            overwrite=args.overwrite,
        )
    except (LayerRunError, VisibilityArtifactError, VisibilityContractError) as error:
        print(f"depth-scape-plan: error: {error}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "backgroundDisocclusion": str(artifacts.background_disocclusion),
                "midgroundDisocclusion": str(artifacts.midground_disocclusion),
                "preview": str(artifacts.preview),
                "manifest": str(artifacts.manifest),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
