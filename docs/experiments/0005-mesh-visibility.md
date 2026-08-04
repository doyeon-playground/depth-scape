# 0005: Mesh visibility and adaptive boundary refinement

- **Status:** Bounded visibility baseline complete; completion contract pending
- **Date:** 2026-08-05
- **Owner:** DepthScape

## Question

Can the continuous relative-depth mesh preserve the observed source view and
measure newly exposed holes during bounded horizontal motion without broad
artificial gaps at depth boundaries?

This experiment does not generate hidden RGB or depth, select the final Python
rendering toolkit, or claim that three sampled positions prove coverage over a
continuous camera path.

## Implementation

The mesh builder first detects base-grid cells whose source depth contains a
jump above the configured threshold. Instead of discarding each complete cell,
it subdivides those cells at source-pixel resolution and removes only residual
pixel-scale triangles that still cross the threshold. Unaffected cells keep the
coarse aspect-correct grid. `--no-boundary-refinement` reproduces the earlier
whole-cell behavior, and `--max-refined-source-cells` bounds additional work.

The renderer validates mesh paths, hashes, array formats, dtypes, shapes, face
indices, and configured resource limits before rasterization. It uses a
deterministic orthographic CPU z-buffer in which larger relative Z is nearer.
Camera position is normalized to `[-1, 1]`. The default samples positions
`-1`, `0`, and `1`; endpoint displacement is 2% of render width capped at 64
render pixels, and output is limited to 512 pixels on its longest side.

Position `0` is the observed source composition and is exported directly from
the normalized observed texture at render resolution. Mesh-only holes at that
position are disclosed separately instead of being hidden by the observed
image.

## Reproduction

```bash
python -m pip install -e ".[depth]"
depth-scape-depth INPUT.jpg --output-dir runs/depth
depth-scape-mesh INPUT.jpg \
  --depth-run-dir runs/depth \
  --output-dir runs/mesh
depth-scape-render \
  --mesh-run-dir runs/mesh \
  --output-dir runs/mesh-camera
```

The command records exact configuration, source and artifact hashes, pixel
counts, and timings in `mesh-camera.json`. User media and generated artifacts
remain under the ignored `runs/` directory.

## Output contract

| File | Contract | Provenance |
| --- | --- | --- |
| `center-view.png` | Observed RGB at render resolution | Observed |
| `left-view.png` | Mesh RGB at camera position `-1`; black where missing | Observed texture projected through inferred geometry |
| `right-view.png` | Mesh RGB at camera position `+1`; black where missing | Observed texture projected through inferred geometry |
| `center-geometry-holes.png` | Source-view mesh gaps; `255=missing`, `0=covered` | Inferred diagnostic |
| `left-view-holes.png` | Missing viewport pixels at position `-1` | Inferred diagnostic |
| `right-view-holes.png` | Missing viewport pixels at position `+1` | Inferred diagnostic |
| `all-view-holes.png` | Union of missing pixels at sampled non-default positions | Inferred diagnostic |
| `mesh-camera.json` | Schema, camera contract, hashes, counts, timing, warnings | Metadata |

The union mask is viewport-space evidence only. It is not yet a source-space
request for an inpainting model and contains no generated content.

## Verification performed

The model-independent suite contains 39 passing unit and integration tests.
Coverage includes safe mesh-run loading, path and hash validation, dtype and
shape contracts, deterministic z-buffer visibility, depth ordering, camera
bounds, source-view preservation, hole-mask semantics, adaptive boundary
refinement, the legacy comparison mode, resource caps, and artifact metadata.
Ruff lint and format checks pass for `pipeline` and `tests`.

## Local mountain observation

The uncommitted 2000x1333 user-provided mountain photograph was evaluated
locally. The source and outputs remain ignored. Both runs used Python 3.12.13,
NumPy 2.3.5, a 384-vertex maximum base dimension, depth-jump threshold `0.02`,
a 512x341 render, three camera positions, and a 10-pixel endpoint shift.

| Measurement | Whole-cell cut | Adaptive refinement |
| --- | ---: | ---: |
| Vertices | 74,705 | 117,706 |
| Faces | 146,538 | 192,530 |
| Mesh build time | 0.122 s | 0.248 s |
| Base cells detected | 879 | 879 |
| Refined source cells | 0 | 31,584 |
| Residual cut source cells | not applicable | 8,588 |
| Center geometry holes | 1.174% | 0.321% |
| Left-view holes | 1.774% | 0.931% |
| Right-view holes | 1.716% | 0.866% |
| Sampled-view union holes | 2.812% | 1.723% |
| Three-view CPU render time | 39.195 s | 50.109 s |

Adaptive refinement reduced source-view geometry holes by about 73% and the
sampled-view union by about 39%. The broad black bands produced by whole-cell
removal became thin boundary gaps, while both the distant snowy mountain and
the nearer ridges remained represented. The cost was 45,992 additional faces,
roughly double mesh-build time, and about 11 seconds more for the unoptimized
three-view CPU render.

## Known limitations and decision

- The CPU rasterizer is an accuracy baseline, not an interactive renderer.
- Three finite positions do not prove visibility for every continuous camera
  position.
- Viewport-space holes do not identify a coherent far surface or its hidden
  depth; using them directly for RGB-only inpainting would risk depth and edge
  inconsistency.
- Relative depth remains unitless visual geometry rather than metric depth.
- One global jump threshold can still miss gradual boundaries or react to noisy
  depth estimates.
- The input contains only visible source geometry; no hidden region is treated
  as recovered reality.

Proceed to a completion-request design that couples hidden RGB and depth,
preserves generated-region provenance, and covers only the bounded camera range.
Do not begin model integration until that contract is explicit and testable.
