# Roadmap

This roadmap describes outcomes, not fixed release dates. DepthScape advances
only when each phase produces a reproducible result with documented failure
cases.

## Phase 0: Scope and baselines

- Fix the product boundary at one landscape photo and limited 2.5D motion.
- Verify candidate model source, version, weight license, and hardware needs.
- Select small, redistributable landscape samples with difficult edge cases.
- Define observed, inferred, and generated pixel provenance.
- Document image, depth, mask, layer, and camera coordinate conventions.
- Establish a reproducible local or Colab experiment workflow.

**Exit condition:** one documented command or notebook produces a depth map from
a sample image and records all configuration needed to repeat the result.

## Phase 1: Relative-depth baseline

- Validate JPG and PNG inputs, orientation, aspect ratio, and size limits.
- Run a candidate monocular relative-depth model.
- Export a visual depth preview and compact run metadata.
- Add numeric tests for transforms, normalization, and shape contracts.
- Record failure cases such as sky, thin branches, water, and reflections.

**Exit condition:** the same input and configuration produce structurally
consistent depth artifacts across repeated runs on a supported environment.

## Phase 2: Layer and occlusion construction

- Derive foreground, midground, and background masks from depth and edges.
- Preserve thin structures where practical.
- Define a bounded horizontal camera range.
- Calculate disocclusion masks for that camera range.
- Build a Layered Depth Image or equivalent inspectable representation.

**Exit condition:** moving the virtual camera exposes known hole masks while the
default viewpoint still matches the source composition.

## Phase 3: Background completion

- Evaluate a candidate RGB inpainting model on the required hole masks.
- Add a strategy for coherent hidden depth, not color alone.
- Preserve provenance masks for every generated pixel.
- Prevent generated content outside the supported movement range from being
  presented to the user.
- Compare seams, repeated textures, depth ordering, and edge stability.

**Exit condition:** the documented landscape samples have complete color and
depth coverage inside the allowed camera range, with generated regions clearly
identified.

## Phase 4: Local Python viewer

- Package textures, masks, layers, camera bounds, and metadata as a scene.
- Add horizontal parallax, reset, reduced-motion, and keyboard controls.
- Add source, depth, layer, and generated-region inspection modes.
- Localize the user-facing workflow in supported languages.
- Select the smallest suitable Python GUI/rendering toolkit through a measured
  prototype.
- Validate supported desktop Python environments and define graceful graphics
  capability errors.

**Exit condition:** a user can create and inspect a bounded 2.5D scene through
one coherent local workflow.

## Phase 5: Quality and optional learning

- Benchmark time, memory, seams, depth ordering, and visual stability.
- Build a categorized failure set without private user media.
- Consider a small DepthScape-specific correction model only for a measured
  baseline limitation.
- Add export and compatibility tests once the scene contract is stable.
- Package a reproducible release and public demonstration.

**Exit condition:** the project has documented supported scenes, failure cases,
resource expectations, and a justified decision about custom training.

## Permanently excluded

- Video reconstruction and temporal fusion.
- Live-camera capture or real-time SLAM.

## Explicitly deferred

- Unrestricted 3D navigation.
- Metric reconstruction and hidden-surface ground truth.
- Large-model training from scratch.
- Cloud accounts, synchronization, and retained uploads.
