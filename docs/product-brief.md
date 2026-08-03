# Product brief

## Summary

ScenePort turns visual captures into interactive 3D scenes. It begins with a
single photo, progresses to video-based reconstruction, and ultimately targets
camera-connected spatial capture.

## Problem

Photos and videos preserve appearance but are usually consumed as flat media.
Existing 3D reconstruction workflows can require specialized capture rigs,
careful multi-view acquisition, expert tools, or long processing pipelines.
ScenePort explores a simpler path from familiar visual inputs to an explorable
spatial result.

## Product principles

- **Progressive capability:** photo first, video second, live camera third.
- **Honest output:** distinguish inferred geometry from observed geometry.
- **Fast feedback:** show intermediate artifacts such as the source image and
  depth map instead of hiding the pipeline.
- **Portable results:** prefer documented, interoperable scene formats.
- **Accessible interaction:** the first useful result should open in a web
  browser without requiring a 3D authoring tool.
- **Privacy by design:** document where inputs are processed and stored before
  any hosted workflow is introduced.

## Primary users

- A creator who wants to turn a landscape or room photo into an interactive
  visual experience.
- A developer or researcher comparing depth and reconstruction approaches.
- A future camera user who wants immediate spatial context from a live scene.

## Photo MVP user story

As a user, I can select a supported image, start reconstruction, inspect the
estimated depth, and explore the generated scene in 3D so that I can understand
both the visual result and its limitations.

## Functional scope

### Input

- One local JPG or PNG image.
- Clear validation and error messages for unsupported or corrupt inputs.
- Explicit orientation handling so previews and reconstruction agree.

### Processing

- Preprocess the image without silently changing its aspect ratio.
- Estimate relative monocular depth.
- Unproject color and depth into colored 3D points or an equivalent initial
  representation.
- Apply minimal cleanup that can be disabled for comparison.

### Output

- Show the original image and estimated depth map.
- Render an interactive 3D scene with orbit, pan, zoom, and reset controls.
- Label the result as inferred rather than measured geometry.
- Report failures without losing the selected input.

## Acceptance criteria for the first demo

- A user can complete the flow with at least one documented sample image.
- The generated scene retains recognizable colors and composition.
- Camera controls remain usable on a current desktop browser.
- The UI exposes processing, success, and failure states.
- The README documents how to reproduce the demo locally.
- No private user image is committed to the repository by default.

## Non-goals for the photo MVP

- Recovering geometry behind visible surfaces.
- Guaranteeing metric depth or survey-grade accuracy.
- Reconstructing every image category equally well.
- Real-time processing.
- Collaborative editing, user accounts, or cloud synchronization.
- Production deployment or long-term storage of uploads.

## Risks and open questions

- Depth discontinuities may stretch foreground colors into the background.
- Sky, reflections, transparency, and textureless regions can produce unstable
  geometry.
- Large inputs may exceed practical memory or latency limits.
- The first 3D representation and export format still need an experiment-led
  decision.
- Model license, model size, hardware support, and local-versus-server inference
  must be evaluated before implementation is locked.

## Success signals

The first milestone is successful when a new contributor can run the documented
flow, generate a recognizable scene from a sample photo, inspect its depth map,
and explain the result's limitations.
