# Architecture

## Status

This document defines a technology-neutral architecture for a single landscape
photo and a limited 2.5D viewer. It does not commit the project to a framework,
deployment provider, or fixed model dependency.

## Data flow

```text
Landscape image
    |
    v
Validation and orientation normalization
    |
    v
Relative-depth estimation
    |
    v
Edge-aware foreground / midground / background layers
    |
    v
Camera bounds and disocclusion masks
    |
    v
Hidden RGB and depth completion
    |
    v
Layered scene package with provenance
    |
    v
Limited-parallax viewer
```

## Logical components

### Image ingestion

- Accepts one local JPG or PNG file.
- Treats media and metadata as untrusted.
- Validates format, dimensions, orientation, and resource limits before model
  inference.
- Preserves the original file and records every deliberate transform.

### Depth adapter

- Exposes a small interface around the selected relative-depth model.
- Returns a documented array shape, numeric range, and invalid-pixel behavior.
- Keeps model download, device choice, and precision outside import-time logic.
- Records model identifier, version, weight checksum where practical, and
  license notes.

### Layer builder

- Combines relative depth with image edges to derive ordered scene layers.
- Keeps masks pixel-aligned with the normalized source image.
- Identifies thin structures and ambiguous edges as explicit diagnostics.
- Produces observed-region masks before any generated content is introduced.

The provisional baseline first smooths relative depth inside low-edge regions,
preserves strong RGB or depth discontinuities, and clusters the result into
three ordered depth groups. It validates the source hash and normalized
dimensions against the producing depth run before processing.

| Artifact | Current contract |
| --- | --- |
| `layer-depth.npy` | float32 HxW edge-refined relative depth in `[0, 1]` |
| `boundary-strength.npy` | float32 HxW RGB/depth edge union in `[0, 1]` |
| `layer-map.npy` | uint8 HxW; `0=background`, `1=midground`, `2=foreground` |
| `*-mask.png` | uint8 HxW; `255=included`, `0=excluded` |
| `layer-preview.png` | RGB diagnostic palette; display only |
| `layers.json` | hashes, coordinate convention, parameters, results, and warnings |

The three masks are mutually exclusive and exhaustive. Their labels express
relative ordering only; they do not identify objects, metric ranges, or hidden
surfaces. Per-pixel data remains in binary artifacts rather than JSON.

### Visibility planner

- Defines the supported virtual camera range.
- Calculates which background regions become visible within those bounds.
- Requests completion only for the union of required disocclusion regions.
- Rejects or clamps camera movement outside generated coverage.

### Completion adapters

- Generate RGB content only inside requested masks.
- Provide hidden-depth estimates or layer-depth rules for the same regions.
- Preserve separate provenance masks for observed, inferred, and generated data.
- Keep candidate models replaceable until experiments justify a dependency.

### Scene packager

- Packages source-derived textures, generated textures, depth, masks, layers,
  camera bounds, warnings, and compact metadata.
- Keeps large arrays and images in binary artifacts rather than embedding them
  in JSON.
- Makes generated artifacts disposable and reproducible from the source plus
  versioned configuration.

### Viewer

- Consumes the scene contract rather than model-specific tensors.
- Supports bounded horizontal parallax, reset, keyboard navigation, and a
  reduced-motion path.
- Can display generated-region provenance without relying on color alone.
- Prevents free-orbit navigation that would expose unsupported geometry.

The first experiment may run as local scripts or notebooks. A network service
should be introduced only if a later product decision requires it.

## Scene representation

A Layered Depth Image is the initial conceptual representation: multiple color,
depth, and mask layers viewed from a constrained camera. The first experiment
may use textured planes or a small depth mesh as long as the boundaries above
remain explicit.

The coordinate system, depth normalization, layer ordering, and camera limits
must be documented before artifacts are treated as compatible.

## Compact manifest

The JSON manifest stores identifiers, dimensions, coordinate conventions,
artifact paths, and warnings. It must not contain model weights, per-pixel depth,
point arrays, or image bytes.

```json
{
  "schemaVersion": "0.1",
  "source": {
    "width": 0,
    "height": 0,
    "mediaType": "image/jpeg"
  },
  "models": {
    "depth": "candidate@version",
    "inpainting": "candidate@version"
  },
  "scene": {
    "representation": "layered-depth-image",
    "depthType": "relative",
    "cameraRange": { "horizontal": 0.0 }
  },
  "artifacts": {
    "depth": "depth.bin",
    "layers": "layers.bin",
    "provenanceMask": "provenance.png"
  },
  "warnings": []
}
```

The final binary formats and coordinate values remain experimental.

## Invariants

- The default viewpoint preserves the source composition.
- Every generated pixel is distinguishable from observed input in provenance
  data.
- RGB, depth, and masks share an explicit alignment transform.
- Layer ordering is deterministic for a fixed input and configuration.
- Camera bounds never exceed generated color and depth coverage.
- Model failures are explicit and never silently replaced with plausible output.
- User media does not become a fixture, log payload, or committed artifact.

## Quality attributes

- **Truthfulness:** generated content is disclosed and never called recovered
  reality.
- **Reproducibility:** versions, configuration, seeds, and transforms are
  recorded.
- **Coherence:** color completion, depth completion, masks, and layer order agree.
- **Portability:** model- and hardware-specific implementations remain isolated.
- **Privacy:** processing is local by default and retention is minimized.
- **Accessibility:** motion is optional and all controls have keyboard paths.
- **Internationalization:** English is a fallback rather than embedded UI text.
