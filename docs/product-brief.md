# Product brief

## Summary

DepthScape turns one landscape photograph into an explorable 2.5D scene. It
combines relative-depth estimation, image layering, constrained inpainting, and
a local Python parallax viewer to create a spatial impression from a flat
image.

## Problem

A landscape photo preserves appearance from one viewpoint but cannot provide
the visual separation that appears when an observer moves. A full 3D
reconstruction cannot be recovered from one image because hidden surfaces were
never captured. DepthScape therefore targets a smaller and more honest result:
a controlled 2.5D experience that generates only the small hidden regions
revealed by limited camera motion.

## Product principles

- **Honest synthesis:** always distinguish observed pixels from generated
  pixels and avoid calling generated content a reconstruction of reality.
- **Constrained motion:** limit the camera before expanding or inventing large
  unseen regions.
- **Depth coherence:** prioritize stable layer boundaries and plausible
  occlusion over dramatic movement.
- **Reproducibility:** record input transforms, model identifiers, parameters,
  and artifact relationships.
- **Inspectable pipeline:** expose source, depth, masks, and generated-region
  previews where useful.
- **Local-first privacy:** process user images locally by default and document
  any future remote processing before it is introduced.
- **Accessible interaction:** support keyboard operation and non-motion ways to
  inspect the result.

## Primary users

- A creator who wants subtle depth and parallax from a landscape photo.
- A developer studying monocular depth, occlusion, and layered image rendering.
- A learner who wants to inspect how depth and inpainting form a 2.5D scene.

## Core user story

As a user, I can select a landscape photo, inspect its estimated depth and
layers, and explore a small parallax movement so that I can experience a clear
sense of depth without mistaking generated regions for captured reality.

## Functional scope

### Input

- One local JPG or PNG landscape image.
- Clear validation for media type, dimensions, orientation, and resource limits.
- No automatic upload or long-term retention.

### Processing

- Normalize orientation without silently changing aspect ratio.
- Estimate relative monocular depth.
- Divide the scene into foreground, midground, and background regions using
  depth and edge-aware rules.
- Calculate which pixels become exposed inside the supported camera range.
- Generate only the required background color and depth behind occluders.
- Package textures, masks, geometry, provenance, and warnings as one scene.

### Output

- Preview the original image, relative-depth map, and layer masks.
- Render a bounded horizontal parallax view in a local Python application with
  reset and reduced-motion behavior.
- Provide a generated-region overlay or equivalent disclosure.
- Report failures without losing the selected local input.

## Acceptance criteria for the first demo

- A user can complete the flow with at least one redistributable landscape
  sample.
- The result preserves the source composition from its default viewpoint.
- Limited movement creates visible depth without large holes or severe edge
  tearing in the documented sample.
- The generated-region disclosure remains available in the viewer.
- Camera bounds prevent the user from revealing regions outside the generated
  support.
- Processing, success, and failure states are accessible and localized.
- The README documents a reproducible local workflow.
- No private image, model weight, or generated scene is committed by default.

## Non-goals

- Recovering the true content behind visible objects.
- Full 3D geometry or free-orbit navigation.
- Metric depth or survey-grade accuracy.
- Indoor, portrait, object-centric, video, or live-camera workflows. Video and
  live capture are permanently excluded rather than later expansion stages.
- Real-time capture, user accounts, cloud synchronization, or hosted storage.
- Training a large foundation model during the initial milestone.

## Risks and open questions

- Thin structures, sky boundaries, reflections, transparency, and textureless
  regions may create unstable depth or masks.
- RGB inpainting alone does not provide coherent hidden depth; the completion
  strategy must generate or infer both.
- Larger camera motion rapidly increases invented content and edge artifacts.
- Existing model weights may have licenses that restrict redistribution or
  commercial use.
- Desktop graphics capability, packaging behavior, and local inference
  performance will vary across supported Python environments.
- The initial layered representation and export contract still require a
  measured experiment.

## Success signal

The first milestone succeeds when a new contributor can reproduce a landscape
demo, inspect every generated artifact, distinguish observed from synthesized
content, and explore the result within a safe camera range.
