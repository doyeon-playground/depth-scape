# 0006: Coupled hidden-surface completion requests

- **Status:** Completion-request baseline complete; model evaluation pending
- **Date:** 2026-08-05
- **Owner:** DepthScape

## Question

Can finite z-buffered viewport holes from the cut continuous mesh be converted
into coherent, provenance-aware RGB and relative-depth requests without using
semantic classes or replacing observed source pixels?

This experiment defines requests and depth constraints only. It does not run an
inpainting model, claim hidden ground truth, package a final scene, or select the
Python viewer toolkit.

## Contract

The planner consumes in-memory coverage and depth buffers aligned with sampled
camera positions. Interior holes are inverse-projected into a canonical hidden
surface. Positive camera positions expect nearer support on the left and
negative positions expect it on the right. A bounded local 2D depth
neighborhood handles diagonal and non-horizontal boundaries when immediate
horizontal support is inconclusive.

Frame holes inverse-project either outside or inside the observed source grid:

- outside coordinates become horizontal overscan requests;
- inside coordinates become observed edge-seam support, which reuses observed
  RGB with inferred support depth; and
- holes without either mapping remain unresolved and prevent a sampled-view
  readiness claim.

Generated RGB and float32 relative depth always share the exact request mask.
The hidden-surface mask is separate from observed texture, and the overscan mask
is always false inside the observed center columns. Per-pixel arrays remain PNG
or NPY artifacts rather than JSON payloads.

Automatic camera sampling selects an odd count such that nearest-surface motion
between samples is at most two render pixels, unless the 33-position cap is
reached. An explicit odd `--sampled-positions` value remains available for
controlled comparisons. Finite samples do not prove every subpixel position.

## Reproduction

```bash
python -m pip install -e ".[depth]"
depth-scape-depth INPUT.jpg --output-dir runs/depth
depth-scape-mesh INPUT.jpg \
  --depth-run-dir runs/depth \
  --output-dir runs/mesh
depth-scape-hidden \
  --mesh-run-dir runs/mesh \
  --output-dir runs/hidden
```

`--max-sample-shift-step-pixels`, `--sampled-positions`,
`--min-depth-separation`, and `--depth-support-radius` expose the measured
planning choices. Existing known artifacts are replaced only with
`--overwrite`.

## Principal artifacts

| File | Contract | Provenance |
| --- | --- | --- |
| `hidden-surface-mask.png` | Canonical pixels requiring RGB and relative depth | Inferred request |
| `hidden-relative-depth-hint.npy` | Far-side float32 hint; NaN outside the mask | Inferred geometry |
| `hidden-depth-ceiling.npy` | Generated depth must remain smaller | Inferred occluder constraint |
| `horizontal-outpaint-mask.png` | Padded pixels requiring RGB and relative depth | Inferred request |
| `horizontal-outpaint-depth-hint.npy` | Nearest-edge continuation hint | Inferred geometry |
| `observed-edge-seam-mask.png` | Source pixels reused with inferred depth support | Observed RGB + inferred geometry |
| `local-depth-support-view-holes.png` | View holes that required local 2D support | Inferred diagnostic |
| `unresolved-view-holes.png` | Sampled holes without a supported mapping | Inferred diagnostic |
| `completion-request-preview.png` | Magenta hidden, cyan overscan, amber seam support | Display only |
| `hidden-surface-plan.json` | Bounds, transforms, hashes, counts, timing, and warnings | Metadata |

No artifact in this experiment contains generated RGB or generated depth.

## Verification performed

The model-independent suite contains 47 passing tests and 42 passing subtests.
Coverage includes configuration and array validation, strict camera ordering,
automatic displacement-based sampling, horizontal and local 2D depth support,
overscan isolation from observed columns, observed seam provenance, coupled
channel requirements, resource caps, safe overwrite behavior, artifact hashes,
and manifest semantics. Ruff formatting and lint checks pass for changed Python
files.

## Local mountain observation

The ignored 2000x1333 user-provided mountain photograph was evaluated locally.
Redistribution permission remains unverified, so neither the source nor run
artifacts are committed. Source SHA-256:
`c16e1790e395bb6257e4613f72d6f8b95b948234dc6c7312e2f77e6c8eba2895`.

| Item | Measured value |
| --- | ---: |
| Implementation revision | `28771c1c5d805d43c107e65889322ec4855fa0e2` |
| Python / NumPy | 3.14.6 / 2.5.1 |
| Render dimensions | 512x341 |
| Camera positions | 11 from `-1` through `+1` |
| Endpoint nearest-surface shift | 10 pixels |
| Maximum sampled shift step | 2 pixels |
| Union viewport holes | 3,464 pixels |
| Canonical hidden request | 894 pixels |
| Horizontal overscan request | 2,007 pixels |
| Total generated RGB/depth request | 2,901 pixels |
| View holes using local 2D depth support | 851 pixels |
| Observed seam support | 41 source pixels for 42 viewport holes |
| Unresolved sampled holes | 0 pixels |
| Supported sampled-hole union | 100% |
| Planning time including 11 CPU renders | 148.872 seconds |

All sampled holes mapped to hidden generation, overscan generation, or observed
seam support. Counts in different viewport categories are union diagnostics and
can overlap at the same viewport coordinate across different camera positions.

## Limitations and next step

- Eleven finite positions reduce but do not eliminate subpixel sampling risk.
- Local 2D depth support is an inference around a discontinuity, not hidden
  truth.
- Overscan assumes that the nearest visible frame-edge surface continues
  outward.
- Seam support still needs scene geometry that combines observed RGB with its
  inferred depth hint.
- The deterministic CPU rasterizer is too slow for the final interactive
  viewer.
- Completion-model quality, license, device requirements, seams, and generated
  depth consistency remain unmeasured.

Proceed to Phase 3 by evaluating a replaceable RGB completion adapter and a
coupled relative-depth strategy against these exact masks. Reject any adapter
that changes observed center pixels, omits generated-depth provenance, or
requires camera motion outside the recorded bounds.
