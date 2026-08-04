# Model baselines

## Purpose

DepthScape will use replaceable pretrained models to establish a measurable
baseline before deciding whether custom training is justified. A candidate is
not a fixed dependency until its exact version, weights, license, runtime, and
failure cases are documented in a reproducible experiment.

## Candidate responsibilities

### Relative depth

**Candidate:** Depth Anything V2 Small

The depth baseline predicts relative depth from one landscape image. The adapter
must record preprocessing, output convention, model identifier, weight source,
checksum where practical, and hardware path. DepthScape must not describe this
output as metric depth without separate evidence.

### RGB completion

**Candidate:** LaMa

The inpainting baseline fills only the background regions required by the
supported camera movement. Its output is generated content, not evidence of the
real hidden scene. Masks, seeds, and configuration must be retained for
reproducibility.

### Hidden-depth completion

RGB inpainting does not solve geometry. The first experiments must compare a
simple layer-depth prior with an explicit depth-completion method. The chosen
approach must preserve foreground/background ordering and avoid placing
generated background in front of its occluder.

## DepthScape-owned logic

The project's initial technical contribution is the reproducible system around
the model baselines:

- image validation and orientation handling;
- depth normalization and edge-aware layer construction;
- camera-bound planning and disocclusion masks;
- color and depth completion orchestration;
- provenance and artifact contracts; and
- a viewer that enforces supported movement.

## Evaluation before adoption

For each candidate, record:

- official source and exact version;
- code and weight licenses separately;
- model and download size;
- device, precision, input size, runtime, and peak memory;
- deterministic settings or known sources of variation;
- output shape, range, and coordinate meaning;
- landscape-specific strengths and failure cases; and
- redistribution and deployment constraints.

Tests should include sky, vegetation, mountains, water, thin structures, low
contrast, and strong foreground occluders.

## Custom-model decision

A custom model is considered only when a baseline limitation is repeatable,
measurable, and important to the target experience. The first custom model
should be the smallest module that addresses that limitation, such as edge-aware
depth correction, layer-mask refinement, or RGB/depth consistency correction.
Training a large foundation model from scratch is not part of the initial plan.
