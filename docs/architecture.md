# Architecture

## Status

This document defines a technology-neutral target architecture. It is not a
commitment to a framework, model, or deployment provider.

## Photo MVP data flow

```text
Image input
    |
    v
Validation and orientation
    |
    v
Preprocessing
    |
    v
Relative depth estimation
    |
    v
3D unprojection and cleanup
    |
    v
Scene artifact and metadata
    |
    v
Interactive viewer
```

## Logical components

### Frontend

- Selects an image and shows a local preview.
- Starts processing and presents progress and failures.
- Compares the source image with the estimated depth map.
- Loads the scene artifact and provides 3D camera controls.
- Presents locale-aware UI without embedding user-facing strings in logic.

### Backend or local orchestrator

- Validates request metadata and coordinates reconstruction jobs.
- Provides explicit job states: queued, processing, succeeded, failed, and
  cancelled when cancellation becomes available.
- Keeps model-specific details out of the client contract.
- Applies input retention and deletion rules when server processing exists.

The first experiment may run as a local script. A network service should be
introduced only when it improves the end-to-end demo.

### Reconstruction pipeline

The pipeline owns deterministic preprocessing, depth inference, 3D conversion,
optional cleanup, artifact creation, and diagnostic metadata. Model adapters
should expose a small shared interface so experiments do not leak throughout
the product.

### Viewer

The viewer consumes a scene artifact rather than a model-specific tensor. It
owns rendering, navigation, reset behavior, loading feedback, and capability
fallbacks.

## Initial boundaries

- The original image is the source input and must not be modified in place.
- Generated artifacts are disposable and should be reproducible from the source
  input plus versioned configuration.
- Model weights are external dependencies and must include source, version,
  checksum where practical, and license notes.
- Sample images must be redistributable and include attribution when required.
- User uploads must never become repository fixtures without explicit consent.

## Proposed artifact metadata

The exact schema will be versioned after the first experiment, but a result
should be able to report:

```json
{
  "schemaVersion": "0.1",
  "source": {
    "width": 0,
    "height": 0,
    "mediaType": "image/jpeg"
  },
  "reconstruction": {
    "method": "monocular-depth",
    "depthType": "relative",
    "representation": "point-cloud"
  },
  "artifacts": {
    "depthPreview": "",
    "scene": ""
  },
  "warnings": []
}
```

Paths and transport details are intentionally unspecified.

## Evolution by input type

### Video

Video adds frame sampling, camera-pose estimation, temporal quality checks, and
multi-view fusion ahead of scene packaging. The viewer contract should remain
stable where possible.

### Live camera

Live capture adds permissions, device management, bounded frame queues,
incremental updates, coverage guidance, cancellation, and stricter privacy and
resource controls.

## Quality attributes

- **Reproducibility:** record configuration and component versions.
- **Observability:** expose stages and actionable failures.
- **Portability:** isolate hardware- and model-specific implementations.
- **Privacy:** minimize retention and make processing location explicit.
- **Accessibility:** support keyboard navigation and non-color-only status cues.
- **Internationalization:** treat English as the fallback, not as text embedded
  throughout the interface.
