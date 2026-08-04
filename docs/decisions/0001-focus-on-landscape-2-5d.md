# 0001: Focus on landscape-photo 2.5D

- **Status:** Accepted
- **Date:** 2026-08-04

## Context

The project began as ScenePort, a broad plan to convert photos, videos, and live
camera feeds into explorable 3D environments. Reproducing or extending a
Glob3R-style system was also considered. That scope required multi-view
geometry, temporal processing, global optimization, substantial engineering,
and training resources beyond the project's current Colab-oriented environment.

A single landscape photo offers a smaller product that can still explore depth,
occlusion, image completion, and spatial rendering. It cannot provide true
hidden geometry, so its output must be explicitly constrained and disclosed.

## Decision

Rename the project to **DepthScape** and focus on this outcome:

> Transform one landscape photo into a layered 2.5D scene with limited parallax,
> while clearly identifying content generated behind visible occluders.

The first implementation will evaluate replaceable pretrained baselines for
relative depth and RGB inpainting. DepthScape will own layer construction,
visibility planning, hidden-depth handling, provenance, scene packaging, and
the bounded viewer.

Video, live camera input, free navigation, metric reconstruction, and large
custom-model training are excluded from the product roadmap.

## Consequences

- The project becomes achievable through small, reproducible experiments.
- Evaluation can focus on depth edges, occlusion, seams, and visual stability.
- Generated hidden content must be treated as synthesis, not reconstruction.
- Camera motion is limited by generated color and depth coverage.
- Existing ScenePort documentation, repository metadata, and translations must
  be updated to the new name and scope.
- A future multi-view project should be proposed as a separate decision rather
  than silently expanding DepthScape.
