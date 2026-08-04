# 0004: Cut continuous-depth mesh baseline

- **Status:** Geometry artifacts ready; rendered camera evaluation pending
- **Date:** 2026-08-04
- **Owner:** DepthScape

## Question

Can deterministic project-owned geometry preserve one photo and its continuous
relative depth while removing mesh connectivity at likely occlusion boundaries,
without requiring semantic classes such as sky or mountain?

This experiment does not select a Python rendering toolkit, move a virtual
camera, generate hidden RGB or depth, or claim metric geometry.

## Baseline

The command validates that the normalized RGB input and depth run share one
source SHA-256 and dimensions. It then:

1. chooses an integer sampling stride whose longest mesh dimension is at most
   384 vertices while retaining the final source border;
2. maps sampled image coordinates to an aspect-correct X/Y plane;
3. stores aligned normalized relative proximity directly as Z;
4. marks both endpoints of every four-connected depth change greater than
   `0.02`;
5. omits both triangles from any sampled grid cell containing a marked source
   pixel; and
6. writes observed RGB separately from the inferred geometry and diagnostics.

No scene category or fixed layer count participates in this process.

## Reproduction

Run the depth baseline first, then build the mesh from the same input:

```bash
python -m pip install -e ".[depth]"
python samples/create_demo_landscape.py demo-landscape.png
depth-scape-depth demo-landscape.png --output-dir runs/demo
depth-scape-mesh demo-landscape.png \
  --depth-run-dir runs/demo \
  --output-dir runs/demo-mesh
```

The maximum mesh dimension, normalized-depth jump threshold, preview overlay
opacity, input limits, and overwrite behavior are explicit CLI options. The
chosen values and measured result are recorded in `mesh.json`.

## Output contract

| File | Contract | Provenance |
| --- | --- | --- |
| `observed-texture.png` | RGB HxW normalized source pixels | Observed |
| `mesh-vertices.npy` | float32 Nx3 aspect-correct X/Y and relative-proximity Z | Derived/inferred |
| `mesh-uv.npy` | float32 Nx2 top-left-origin UV coordinates in `[0, 1]` | Derived |
| `mesh-faces.npy` | int32 Mx3 retained triangle indices | Inferred geometry |
| `mesh-sample-x.npy` | int32 source X coordinate per mesh column | Derived |
| `mesh-sample-y.npy` | int32 source Y coordinate per mesh row | Derived |
| `mesh-cut-cells.png` | uint8 mesh-cell grid; `255=cut`, `0=retained` | Inferred diagnostic |
| `mesh-preview.png` | observed RGB with cut-cell footprints overlaid red | Display only |
| `mesh.json` | schema `0.1`, hashes, coordinates, parameters, metrics, warnings | Metadata |

The mesh uses a right-handed coordinate system. X points right, Y points up,
and larger Z values are nearer. X spans the source aspect ratio, Y spans
`[-1, 1]`, and Z remains the input's unitless `[0, 1]` relative proximity.
Texture UV uses a top-left origin with V pointing down. Faces are
counter-clockwise when viewed from positive Z.

## Verification performed

The model-independent suite contains 28 passing tests. New coverage verifies:

- aspect-correct vertex and UV endpoints;
- deterministic sampling including the final source border;
- counter-clockwise face winding;
- removal of every triangle that would cross a synthetic depth cliff;
- preservation of RGB outside the diagnostic overlay;
- pixel-identical normalized source texture output;
- typed array shapes, provenance, hashes, overwrite protection; and
- rejection of invalid configuration, shape, dtype, and numeric range.

## Local mountain observation

The same uncommitted 2000x1333 user-provided mountain photograph used in prior
experiments was evaluated locally. The source and generated output remain under
the ignored `runs/` directory. Source identity:
`c16e1790e395bb6257e4613f72d6f8b95b948234dc6c7312e2f77e6c8eba2895`.

| Item | Observed value |
| --- | --- |
| Python / NumPy | 3.12.13 / 2.3.5 |
| Depth model | Depth Anything V2 Small, revision `5426e4f0f36572d16453bbda7a8389317b1bef99` |
| Source dimensions | 2000x1333 |
| Mesh sampling stride | 6 source pixels |
| Mesh grid | 335x223 |
| Vertices | 74,705 |
| Retained faces | 146,538 |
| Cut cells | 879 of 74,148, or 1.185% |
| Retained face fraction | 98.815% |
| Mesh build time | 0.122 seconds |
| Measurement environment | Intel64 Family 6 Model 158, 8 logical processors; no separate warm-up |
| Timer scope | Geometry construction only; input decoding and artifact writes excluded |
| Observed texture equality | Pixel-identical to normalized source RGB |

The RGB-preserving preview keeps both the distant snowy mountain and nearer
ridges visible. Red cut footprints follow the distant mountain silhouette,
the nearer dark ridge, and the nearest terrain boundaries without a sky-specific
rule. This is a geometry diagnostic, not yet proof of a correct rendered view.

## Known limitations

- Removing whole sampled cells produces a conservative cut strip. The renderer
  must measure whether that strip creates visible seams at the source viewpoint.
- One global normalized-depth threshold can miss gradual occlusion boundaries
  or react to a noisy depth prediction.
- Mesh sampling reduces geometry resolution while the observed texture remains
  full resolution.
- The artifact contains only visible source geometry. It has no hidden RGB or
  hidden depth behind cut boundaries.
- Camera bounds and completion masks from the former three-layer planner are
  not compatible with this representation.

## Current decision

Continue with a small z-buffered Python rendering experiment using this mesh.
The next experiment must prove source-view preservation, measure holes at a
bounded horizontal camera range, and compare seams with and without depth-edge
cuts. Hidden-content completion remains paused until those measurements exist.
