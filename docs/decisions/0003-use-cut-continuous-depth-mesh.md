# 0003: Use a cut continuous-depth mesh

- **Status:** Accepted
- **Date:** 2026-08-04
- **Owner:** DepthScape

## Context

The first geometry baseline grouped every pixel into three global relative-depth
bands. It was reproducible and useful for planning, but its solid-color preview
made preserved RGB content look absent. More importantly, one global band can
contain multiple surfaces, such as both open sky and a distant mountain, so the
surfaces cannot respond independently to camera motion.

Adding fixed semantic layers such as sky, mountain, and ground would not
generalize to aerial, indoor, urban, or skyless photographs. A semantic model
would also add category coverage, weights, and licensing concerns without
solving the underlying geometric representation problem.

## Decision

DepthScape will use an image-textured continuous relative-depth mesh as the
candidate scene geometry. The mesh:

- retains normalized source RGB as an observed texture;
- uses aspect-correct image-plane X/Y coordinates;
- stores the aligned unitless relative proximity as Z;
- removes triangle connectivity from sampled cells containing a sharp local
  depth jump; and
- records the cut cells separately from observed RGB.

The algorithm does not assign semantic names to regions. A depth discontinuity
may correspond to any occlusion boundary, including terrain, a building, a
person, or an object seen from above.

The three-layer pipeline and its discrete camera planner remain reproducible
comparison baselines. They are not the final scene contract for the Python
viewer, and their completion masks must not be reused for the continuous mesh.

## Consequences

- Gradual relief remains continuous instead of collapsing into three motions.
- Strong depth boundaries no longer force triangles to stretch between front
  and rear surfaces.
- The default scene package retains every observed RGB pixel independently of
  mesh-cut diagnostics.
- The renderer must use a z-buffer and measure newly visible holes across its
  own bounded camera path before hidden-content completion begins.
- The relative-depth Z axis is visual geometry, not metric reconstruction.
- A global cut threshold is only a baseline; thin structures, gradual depth
  transitions, and noisy model edges need a failure-set evaluation.

## Rejected alternatives

### Fixed semantic layers

Rejected because image content and camera orientation are unrestricted within
the single-photo landscape scope. Sky-specific logic cannot handle a skyless or
top-down view.

### More global depth bands

Rejected as the primary representation because increasing the band count does
not preserve continuous relief and still merges disconnected surfaces with
overlapping depth values.

### Fully connected depth grid

Rejected because triangles spanning a strong depth discontinuity visibly
stretch foreground color into the background during camera motion.
