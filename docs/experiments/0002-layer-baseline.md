# 0002: Three-layer construction baseline

- **Status:** Reproducible comparison baseline; superseded for scene geometry
- **Date:** 2026-08-04
- **Owner:** DepthScape

## Question

Can deterministic project-owned logic turn an aligned relative-depth map and
its source RGB image into inspectable background, midground, and foreground
masks without storing per-pixel data in JSON or claiming semantic knowledge?

This experiment does not calculate camera motion, disocclusion holes, hidden
RGB, hidden depth, or a renderable scene.

## Baseline

The baseline validates that the depth run records the same source SHA-256 and
normalized dimensions as the input image. It then:

1. builds a normalized boundary-strength map from RGB luminance and depth
   discontinuities;
2. applies two iterations of 3x3 smoothing in low-edge regions while retaining
   original depth at strong boundaries;
3. summarizes the refined depth in a 4,096-bin histogram;
4. runs deterministic weighted one-dimensional k-means with three clusters;
5. orders the clusters from far to near and exports one exhaustive label map
   plus three binary masks.

The labels mean only `0=background`, `1=midground`, and `2=foreground` in
relative-depth order. They are not semantic classes and do not represent
metric distance.

## Reproduction

Run the depth baseline first, then pass the same image and its completed depth
run to the layer command:

```bash
python -m pip install -e ".[depth]"
python samples/create_demo_landscape.py demo-landscape.png
depth-scape-depth demo-landscape.png --output-dir runs/demo
depth-scape-layers demo-landscape.png \
  --depth-run-dir runs/demo \
  --output-dir runs/demo-layers
```

Use `--overwrite` only to replace the known layer artifacts in an existing
output directory. Histogram size, convergence tolerance, maximum iterations,
smoothing iterations, edge percentile, minimum layer fraction, and resource
limits are explicit CLI options and are recorded in `layers.json`.

## Output contract

All pixel artifacts share the normalized source dimensions and use row-major
`(height, width)` arrays with a top-left origin, x right, and y down.

| File | Contract | Provenance |
| --- | --- | --- |
| `layer-depth.npy` | float32 HxW `[0, 1]`; edge-refined assignment depth | Inferred |
| `boundary-strength.npy` | float32 HxW `[0, 1]`; RGB/depth discontinuity union | Inferred diagnostic |
| `layer-map.npy` | uint8 HxW labels `0`, `1`, or `2` | Inferred |
| `background-mask.png` | uint8 HxW; `255=included`, `0=excluded` | Derived from inferred labels |
| `midground-mask.png` | uint8 HxW; `255=included`, `0=excluded` | Derived from inferred labels |
| `foreground-mask.png` | uint8 HxW; `255=included`, `0=excluded` | Derived from inferred labels |
| `layer-preview.png` | RGB fixed-palette visualization | Display only |
| `layers.json` | schema `0.1`, hashes, parameters, measurements, warnings | Run metadata |

The masks are mutually exclusive and exhaustive. The manifest records the
source image hash, producing depth artifact and manifest hashes, pinned depth
model identity, clustering centers and thresholds, layer fractions, software
revision, and artifact hashes. It contains no image bytes or per-pixel arrays.

## Verification performed

The model-independent suite contains 16 passing tests. Layer coverage includes:

- far-to-near label ordering and exhaustive assignment;
- RGB/depth shape, dtype, finite-range, and dynamic-range validation;
- source hash and normalized-dimension alignment with the depth run;
- rejection of absolute paths, path traversal, NPZ containers, and malformed
  depth artifacts;
- edge-preserving smoothing behavior and the fixed preview palette;
- mutually exclusive masks, artifact hashes, provenance metadata, and explicit
  overwrite protection.

Static checks pass with Ruff formatting and lint rules.

## Local landscape observation

A user-provided 2000x1333 mountain landscape was evaluated locally. The image
is intentionally not committed: redistribution permission has not been
verified, and user media must not become a repository fixture. Its SHA-256 is
recorded only to identify this observation:
`c16e1790e395bb6257e4613f72d6f8b95b948234dc6c7312e2f77e6c8eba2895`.

| Item | Observed value |
| --- | --- |
| Python / NumPy | 3.12.13 / 2.5.1 |
| Depth model | Depth Anything V2 Small, revision `5426e4f0f36572d16453bbda7a8389317b1bef99` |
| Layer implementation revision | `372491c61868064c28f6a700316e0d6d521fa1b1` |
| Layer build time | 0.294 seconds on the local CPU environment |
| Cluster centers, far to near | 0.051318, 0.221213, 0.572231 |
| Thresholds, far to near | 0.136265, 0.396722 |
| Pixel fractions, far to near | 59.64%, 26.30%, 14.06% |
| K-means iterations | 12 |

The preview formed three broad, coherent regions: sky and the distant snowy
mountain, intermediate ridges and slopes, and the near valley terrain. Major
silhouettes were stable and there was no salt-and-pepper fragmentation at this
resolution. The result is suitable as an inspectable baseline for camera-bound
planning, not as a final object-aware layer decomposition.

## Known limitations

- Sky and distant mountain surfaces can share the background cluster because
  the depth model assigns them similar relative values.
- A global three-cluster distribution can divide one continuous surface or
  merge different objects when their estimated depths overlap.
- RGB edges influence smoothing boundaries but do not introduce semantic
  identity or repair an incorrect depth ordering.
- Thin structures, haze, reflections, flat depth distributions, and very small
  layers require broader failure-set evaluation.
- The baseline deliberately rejects an image when any resulting layer is below
  the configured minimum fraction instead of silently returning a misleading
  three-layer result.

## Current decision

Keep this algorithm as a reproducible comparison baseline. Experiment 0004
replaces the fixed three-band representation with a cut continuous-depth mesh
for candidate scene geometry. No semantic meaning should be added to these
historical labels.
