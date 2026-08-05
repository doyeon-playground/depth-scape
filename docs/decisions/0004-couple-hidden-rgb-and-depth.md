# 0004: Couple hidden RGB and relative-depth requests

- **Status:** Accepted
- **Date:** 2026-08-05
- **Owner:** DepthScape

## Context

The cut continuous mesh exposes viewport holes during bounded horizontal
motion. A union of black viewport pixels is not a stable inpainting input:
different camera positions can refer to the same hidden surface, color-only
completion has no geometry for later views, and frame holes do not belong to
the observed source grid.

Semantic categories such as sky, mountain, or ground do not generalize to
top-down, indoor, urban, or skyless inputs. Treating every hole as generated
content would also mislabel frame-touching mesh seams whose RGB coordinate is
still observed in the source image.

## Decision

DepthScape will convert sampled viewport holes into three explicit contracts:

1. A canonical hidden surface behind an occluder. Its generated RGB and
   generated float32 relative depth share one mask. A far-side depth hint and
   exclusive occluder-depth ceiling preserve ordering.
2. A horizontally padded overscan surface outside the observed frame. Its
   generated RGB and depth share one mask and use nearest-edge depth only as a
   continuation hint.
3. Observed edge-seam support when the inverse coordinate remains inside the
   source. It reuses observed RGB and pairs it with separately inferred support
   depth; it is not generated RGB.

Near/far support is determined from depth, not semantic labels. A bounded local
2D neighborhood may support non-horizontal or diagonal discontinuities, and
the manifest records how many viewport holes required that weaker inference.
Observed center pixels are never replaced.

Automatic camera sampling limits nearest-surface displacement between finite
samples to two render pixels by default, capped at 33 positions. This is a
measured finite-path contract, not a mathematical proof for every subpixel
position.

## Consequences

- Completion adapters must return RGB and relative depth for exactly the same
  requested pixels.
- Generated, observed, and inferred provenance remains separable.
- Multiple views can share one canonical hidden request instead of generating
  unrelated viewport images.
- Overscan generation is restricted to the padded region required by bounded
  motion.
- Edge seams can use truthful observed RGB instead of unnecessary synthesis.
- The scene packager and viewer must enforce the recorded camera range and
  reject unresolved sampled holes.
- A later model experiment can replace RGB or depth adapters without changing
  the request coordinate contract.

## Rejected alternatives

### RGB-only viewport inpainting

Rejected because independently filled views can disagree and provide no depth
for parallax or occlusion ordering.

### Semantic background classes

Rejected because content labels are not required to establish depth ordering
and would fail on valid inputs without the expected categories.

### Treat every frame hole as generated

Rejected because some frame-touching gaps inverse-project to observed source
coordinates. Those pixels keep observed-RGB provenance and need inferred
support geometry instead.
