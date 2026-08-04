# 0003: Bounded camera and disocclusion planner

- **Status:** Reproducible comparison baseline; not compatible with mesh geometry
- **Date:** 2026-08-04
- **Owner:** DepthScape

## Question

Can deterministic pixel-space geometry define a small horizontal camera range
and identify every hidden background or midground pixel required within that
range before any content is generated?

This experiment does not generate RGB or depth, package a final scene, or
render the Python viewer.

## Camera contract

- Camera position is normalized to `[-1, 1]`.
- Position `0` is the source viewpoint and applies no layer shifts.
- Position `-1` is the left endpoint; near content shifts right.
- Position `+1` is the right endpoint; near content shifts left.
- Background shift factor is `0`, midground is `0.5`, and foreground is `1`.
- Maximum foreground displacement is 2% of source width with a 64-pixel cap.
- Every integer foreground shift inside the applied range is evaluated.
- Translation clips at the viewport boundary and never wraps pixels.

These values describe a controlled visual effect, not physical camera
intrinsics, world coordinates, or metric motion.

## Reproduction

Run the preceding depth and layer stages, then plan visibility from the layer
run:

```bash
python -m pip install -e ".[depth]"
python samples/create_demo_landscape.py demo-landscape.png
depth-scape-depth demo-landscape.png --output-dir runs/demo
depth-scape-layers demo-landscape.png \
  --depth-run-dir runs/demo \
  --output-dir runs/demo-layers
depth-scape-plan \
  --layer-run-dir runs/demo-layers \
  --output-dir runs/demo-camera
```

The layer loader rejects missing or modified artifacts, absolute paths, path
traversal, incompatible shapes or dtypes, NPZ containers, and maps that do not
contain exactly the three required labels. Existing output is replaced only
with the explicit `--overwrite` option.

## Output contract

| File | Coordinate space | Meaning |
| --- | --- | --- |
| `background-disocclusion-mask.png` | Background source grid | Pixels to complete behind nearer layers |
| `midground-disocclusion-mask.png` | Midground source grid | Pixels to complete behind foreground |
| `all-view-holes.png` | Union of output viewports | Pixels exposed anywhere before completion |
| `left-view-holes.png` | Output viewport at `-1` | Missing pixels at the left endpoint |
| `right-view-holes.png` | Output viewport at `+1` | Missing pixels at the right endpoint |
| `disocclusion-preview.png` | Display diagnostic | Background, midground, and overlap colors |
| `camera-plan.json` | Compact metadata | Bounds, shifts, hashes, counts, timing, warnings |

Every mask is a pixel-aligned uint8 PNG with `255=included` and `0=excluded`.
The background and midground masks belong to different target layers and must
be completed independently. Per-pixel data is not embedded in JSON.

## Verification performed

The model-independent suite contains 23 passing tests. New coverage verifies:

- clipped horizontal translation without wraparound;
- exact preservation of the source composition at camera position `0`;
- every discrete position inside the camera bounds;
- full viewport coverage after applying the planned target-layer masks;
- endpoint and all-path hole diagnostics;
- camera configuration, layer-map integrity, artifact hashes, provenance, and
  overwrite protection; and
- rejection of invalid labels, shapes, dtypes, shifts, ranges, and manifests.

Ruff formatting and lint checks pass.

## Local mountain observation

The same uncommitted 2000x1333 user-provided mountain image from experiment
0002 was evaluated locally. Redistribution permission remains unverified, so
the photo and all generated artifacts stay under the ignored `runs/`
directory. Source identity:
`c16e1790e395bb6257e4613f72d6f8b95b948234dc6c7312e2f77e6c8eba2895`.

| Item | Observed value |
| --- | --- |
| Implementation revision | `3c8f8f07c48952edbc7d6c20639dbde23c6983ab` |
| Python / NumPy | 3.12.13 / 2.5.1 |
| Applied foreground displacement | ±40 pixels |
| Sampled foreground positions | 81 |
| Background completion requirement | 72,365 pixels, 2.714% |
| Midground completion requirement | 22,256 pixels, 0.835% |
| Left endpoint holes before completion | 31,562 pixels, 1.184% |
| Right endpoint holes before completion | 31,589 pixels, 1.185% |
| Planning time | 0.695 seconds on the local CPU environment |

The masks remain concentrated along the two inferred layer boundaries and the
horizontal viewport edges. Their narrow extent supports the current 2% motion
limit. The jagged sections follow layer-map errors rather than planner noise;
completion quality will therefore depend on boundary refinement and padding.

## Current decision

Keep this plan as a reproducible comparison for discrete three-layer motion.
Experiment 0004 changes the candidate scene representation to a cut continuous
mesh, so these masks must not drive its hidden-content completion. A new
z-buffered camera experiment must derive mesh-specific visibility first.
