# Architecture

## Status

This document defines the architecture for a single landscape photo and a
local Python 2.5D viewer. The Python delivery boundary is fixed, while the GUI
and rendering toolkit, scene format, and model dependencies remain replaceable.

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
Continuous relative-depth mesh with depth-edge cuts
    |
    v
Z-buffered camera bounds and disocclusion masks
    |
    v
Hidden RGB and depth completion
    |
    v
Mesh scene package with provenance
    |
    v
Local Python limited-parallax viewer
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

### Geometry builder

- Combines aligned source coordinates with continuous relative depth.
- Keeps masks pixel-aligned with the normalized source image.
- Cuts mesh connectivity at sharp depth changes without semantic classes.
- Identifies cut cells, thin structures, and ambiguous edges as diagnostics.
- Produces observed-region masks before any generated content is introduced.

The candidate scene baseline samples an aspect-correct image plane, assigns the
aligned unitless relative proximity to each vertex's Z coordinate, and omits
triangles from cells containing a local depth jump above the configured
threshold. The normalized observed RGB texture is stored separately and remains
pixel-identical to the input at the source viewpoint.

| Artifact | Current contract |
| --- | --- |
| `observed-texture.png` | uint8 RGB HxW normalized source pixels |
| `mesh-vertices.npy` | float32 Nx3 aspect-correct X/Y and relative-proximity Z |
| `mesh-uv.npy` | float32 Nx2 top-left-origin UV coordinates |
| `mesh-faces.npy` | int32 Mx3 retained triangle indices |
| `mesh-sample-*.npy` | int32 source coordinates sampled by mesh rows and columns |
| `mesh-cut-cells.png` | uint8 mesh-cell grid; `255=cut`, `0=retained` |
| `mesh-preview.png` | source RGB with cut footprints overlaid red; display only |
| `mesh.json` | hashes, coordinate convention, parameters, results, and warnings |

The previous edge-preserving three-cluster layer builder remains available as a
comparison baseline. Its labels express relative ordering only; they do not
identify objects, metric ranges, or hidden surfaces. It is not the final scene
geometry contract. Per-pixel and per-mesh data remains in binary artifacts
rather than JSON.

### Visibility planner

- Defines the supported virtual camera range.
- Calculates which background regions become visible within those bounds.
- Requests completion only for the union of required disocclusion regions.
- Rejects or clamps camera movement outside generated coverage.

The implemented comparison planner uses discrete horizontal layer translation
rather than a physical camera. Camera position is normalized to `[-1, 1]`,
where `0` preserves the source composition. Background remains fixed;
midground moves at half the foreground displacement. The default foreground
limit is 2% of image width with a 64-pixel cap. Every integer foreground shift
in that range is evaluated. These masks are not compatible with the continuous
mesh.

| Artifact | Current contract |
| --- | --- |
| `background-disocclusion-mask.png` | Background source-grid pixels needed behind nearer layers |
| `midground-disocclusion-mask.png` | Midground source-grid pixels needed behind foreground |
| `all-view-holes.png` | Viewport pixels exposed at any supported position before completion |
| `left-view-holes.png` | Missing viewport pixels at camera position `-1` |
| `right-view-holes.png` | Missing viewport pixels at camera position `+1` |
| `disocclusion-preview.png` | Fixed-palette target-layer diagnostic; display only |
| `camera-plan.json` | Bounds, shifts, hashes, pixel counts, timing, and warnings |

All comparison masks are uint8 PNG files with `255=included` and `0=excluded`.
The next geometry experiment must replace them with z-buffered mesh visibility
and prove the source view before completion begins.

### Completion adapters

- Generate RGB content only inside requested masks.
- Provide hidden-depth estimates or layer-depth rules for the same regions.
- Preserve separate provenance masks for observed, inferred, and generated data.
- Keep candidate models replaceable until experiments justify a dependency.

### Scene packager

- Packages source-derived textures, generated textures, depth, masks, mesh geometry,
  camera bounds, warnings, and compact metadata.
- Keeps large arrays and images in binary artifacts rather than embedding them
  in JSON.
- Makes generated artifacts disposable and reproducible from the source plus
  versioned configuration.

### Viewer

- Runs as a local Python application; a browser frontend is not part of the
  product plan.
- Consumes the scene contract rather than model-specific tensors.
- Supports bounded horizontal parallax, reset, keyboard navigation, and a
  reduced-motion path.
- Can display generated-region provenance without relying on color alone.
- Prevents free-orbit navigation that would expose unsupported geometry.

Experiments may run as local scripts or notebooks. The viewer must not require
a network service, account, browser runtime, or retained upload.

## Scene representation

The candidate representation is a continuous image-textured depth mesh with
connectivity removed at sharp relative-depth discontinuities. It uses no fixed
semantic layer count. Observed texture, inferred geometry, future generated
coverage, and provenance remain separate artifacts viewed from a constrained
camera.

The coordinate system, depth normalization, face topology, renderer transform,
and camera limits must be documented before artifacts are treated as
compatible.

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
    "representation": "cut-continuous-depth-mesh",
    "depthType": "relative",
    "cameraRange": { "horizontal": 0.0 }
  },
  "artifacts": {
    "depth": "depth.bin",
    "vertices": "mesh-vertices.npy",
    "faces": "mesh-faces.npy",
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
- Mesh sampling and topology are deterministic for a fixed input and configuration.
- Camera bounds never exceed generated color and depth coverage.
- Model failures are explicit and never silently replaced with plausible output.
- User media does not become a fixture, log payload, or committed artifact.

## Quality attributes

- **Truthfulness:** generated content is disclosed and never called recovered
  reality.
- **Reproducibility:** versions, configuration, seeds, and transforms are
  recorded.
- **Coherence:** color completion, depth completion, masks, and mesh visibility agree.
- **Portability:** model- and hardware-specific implementations remain isolated.
- **Privacy:** processing is local by default and retention is minimized.
- **Accessibility:** motion is optional and all controls have keyboard paths.
- **Internationalization:** English is a fallback rather than embedded UI text.
