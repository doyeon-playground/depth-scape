# Roadmap

This roadmap describes outcomes, not fixed release dates. Each phase should
produce a usable demonstration before the next phase expands the input type.

## Phase 0: Foundation

- Agree on terminology, product scope, and reconstruction claims.
- Record candidate depth and 3D representation experiments.
- Define a small set of redistributable sample images and expected artifacts.
- Establish formatting, tests, and a reproducible local setup.

**Exit condition:** one documented experiment can turn a sample image into a
viewable local 3D artifact.

## Phase 1: Photo to 3D

- Add image validation and preprocessing.
- Generate and preview relative depth.
- Produce colored 3D geometry from one image.
- Build an interactive viewer with orbit, pan, zoom, and reset.
- Display progress, errors, and reconstruction limitations.
- Document local setup and the demo workflow.

**Exit condition:** a user can select a photo and explore the inferred scene in
one coherent workflow.

## Phase 2: Video to 3D

- Extract and sample video frames.
- Estimate camera motion and reject unsuitable frames.
- Combine multi-view observations into a more consistent scene.
- Add progress reporting, cancellation, and quality diagnostics.
- Compare the video result with the single-image baseline.

**Exit condition:** a documented capture sequence produces a scene that is more
complete or view-consistent than the photo baseline.

## Phase 3: Camera-connected capture

- Add camera permission and device-selection flows.
- Provide capture guidance and coverage feedback.
- Incrementally update the scene from incoming frames.
- Define latency, privacy, storage, and hardware support expectations.

**Exit condition:** a supported camera can update a spatial preview during a
guided capture session.

## Phase 4: Product hardening

- Benchmark representative devices and scenes.
- Add export, metadata, and compatibility tests.
- Improve accessibility and all supported locales.
- Define secure retention and deletion behavior for any hosted inputs.
- Package a reproducible release and public demo.

## Deferred decisions

The following choices should be made after small experiments rather than fixed
during planning:

- depth-estimation model;
- point cloud, mesh, radiance field, or Gaussian-based representation;
- local, server, or hybrid inference;
- native versus browser-based camera capture; and
- final export formats and hosting platform.
