# DepthScape

**Turn a landscape photo into an explorable 2.5D scene.**

DepthScape is an open-source project that transforms one landscape photo into a
depth-aware scene. It estimates continuous relative depth, cuts mesh
connectivity at likely occlusion boundaries, fills only the small regions
revealed by camera motion, and renders a controlled parallax view in a local
Python application.

> [!IMPORTANT]
> DepthScape does not recover the real content behind an object. Hidden regions
> are generated from visible context and must be presented as AI-inferred
> content. The result is a 2.5D visual experience, not a complete or metrically
> accurate 3D reconstruction.

## Languages

English is the source language for the project and its documentation.

- [한국어](docs/i18n/README.ko.md)
- [日本語](docs/i18n/README.ja.md)
- [简体中文](docs/i18n/README.zh-CN.md)
- [Español](docs/i18n/README.es.md)

## Target experience

```text
Landscape photo
    -> relative depth map
    -> continuous image-textured depth mesh
    -> depth-discontinuity cuts
    -> bounded-camera hole masks
    -> hidden RGB and depth completion
    -> provenance-aware 2.5D scene
    -> local Python parallax viewer
```

The first viewer will constrain camera movement to a small, documented range.
This keeps generated regions limited and reduces tearing around depth edges.

## Initial model baselines

DepthScape will begin by evaluating existing pretrained models instead of
training a large model from scratch:

- **Depth Anything V2 Small** as a candidate relative-depth baseline;
- **LaMa** as a candidate RGB inpainting baseline; and
- deterministic geometry and compositing code owned by DepthScape.

Exact versions, weight licenses, hardware requirements, and replacement options
must be verified in a reproducible experiment before they become fixed project
dependencies. A small DepthScape-specific correction model may be considered
only after the baseline exposes a measurable gap.

## Scope

The first release will:

- accept one local JPG or PNG landscape image;
- preserve its orientation and aspect ratio;
- preview relative depth and depth-boundary cuts without hiding source RGB;
- generate only the hidden regions needed for the allowed camera motion;
- distinguish observed pixels from generated pixels;
- render a keyboard-accessible, limited parallax view; and
- retain enough configuration metadata to reproduce the result.

Video reconstruction and live camera capture will not be added to DepthScape.
Unrestricted camera movement, metric depth, and full hidden-surface
reconstruction are also outside the project scope.

## Project status

DepthScape is currently in the **baseline-evaluation** stage. Reproducible
relative-depth and cut continuous-mesh pipelines are available, together with
a bounded, z-buffered Python rendering baseline. The earlier three-layer
pipeline remains only for reproducible comparison. The next experiment will
turn measured mesh disocclusions into coherent hidden-surface completion
requests before generating any RGB or depth.

## Try the depth and mesh baselines

The baseline validates one JPG or PNG, applies its EXIF orientation, runs the
pinned Depth Anything V2 Small checkpoint, and writes an aligned float32 depth
artifact, an 8-bit preview, and a JSON run record.

```bash
python -m pip install -e ".[depth]"
python samples/create_demo_landscape.py demo-landscape.png
depth-scape-depth demo-landscape.png --output-dir runs/demo
depth-scape-mesh demo-landscape.png \
  --depth-run-dir runs/demo \
  --output-dir runs/demo-mesh
depth-scape-render \
  --mesh-run-dir runs/demo-mesh \
  --output-dir runs/demo-mesh-camera

# Optional comparison with the earlier three-layer baseline
depth-scape-layers demo-landscape.png \
  --depth-run-dir runs/demo \
  --output-dir runs/demo-layers
depth-scape-plan \
  --layer-run-dir runs/demo-layers \
  --output-dir runs/demo-camera
```

The first run downloads a 99.2 MB model checkpoint. CUDA is used when available;
otherwise the command follows a slower CPU-safe path. Input images stay on the
machine running the command. The numeric output is unitless relative proximity,
where larger values mean nearer content; it is not metric depth.

The mesh command validates that the depth run belongs to the same normalized
image, samples an aspect-correct continuous surface, and detects coarse cells
containing sharp local depth jumps. Those cells are refined at source-pixel
resolution so only residual pixel-scale crossings lose their triangles. It
exports the pixel-identical observed texture separately from inferred geometry
and renders an RGB-preserving cut diagnostic. It does not classify sky,
terrain, or other semantic content. The former whole-cell behavior remains
available through `--no-boundary-refinement` for comparison. See
[experiment 0004](docs/experiments/0004-continuous-depth-mesh.md) for the
original geometry contract.

The render command safely validates a mesh run and rasterizes three bounded
horizontal camera positions with a deterministic CPU z-buffer. Camera position
is normalized to `[-1, 1]`; position `0` is the observed source composition,
while the endpoint views reveal currently unsupported pixels. It exports the
center and endpoint views, separates source-view geometry gaps from movement
disocclusions, and records the sampled camera contract in `mesh-camera.json`.
The default output is limited to 512 pixels on its longest side and is an
accuracy baseline rather than the final interactive renderer. See
[experiment 0005](docs/experiments/0005-mesh-visibility.md) for measured
coverage and runtime.

The layer and planning commands remain available as reproducible comparison
baselines. Their fixed three-band camera and completion masks are not the final
mesh scene contract.

The planning command keeps the background fixed, moves the midground at half
the foreground displacement, and inspects every integer foreground shift in a
bounded range. It writes the per-layer regions that require hidden-content
completion, endpoint hole diagnostics, and `camera-plan.json`. This is a
pixel-space comparison contract for the superseded three-layer geometry, not a
physical camera model or the new mesh camera plan.

For a hosted experiment, open the
[Depth baseline notebook](notebooks/0001_depth_baseline.ipynb) in Colab. A Colab
upload is transferred to that temporary Colab runtime, so do not use sensitive
media there. See the [experiment record](docs/experiments/0001-depth-baseline.md)
for the exact model revision, weight digest, artifact contract, and known risks.

## Documentation

- [Product brief](docs/product-brief.md)
- [Roadmap](docs/roadmap.md)
- [Architecture](docs/architecture.md)
- [Model baselines](docs/model-baselines.md)
- [Depth baseline experiment](docs/experiments/0001-depth-baseline.md)
- [Layer baseline experiment](docs/experiments/0002-layer-baseline.md)
- [Camera and disocclusion experiment](docs/experiments/0003-disocclusion-planner.md)
- [Continuous-depth mesh experiment](docs/experiments/0004-continuous-depth-mesh.md)
- [Mesh visibility and boundary-refinement experiment](docs/experiments/0005-mesh-visibility.md)
- [Scope decision](docs/decisions/0001-focus-on-landscape-2-5d.md)
- [Python viewer decision](docs/decisions/0002-use-local-python-viewer.md)
- [Continuous-depth mesh decision](docs/decisions/0003-use-cut-continuous-depth-mesh.md)
- [Internationalization](docs/i18n.md)
- [Contributing](CONTRIBUTING.md)

## Planned repository structure

```text
depth-scape/
|-- viewer/         # Local Python workflow and limited-parallax viewer
|-- pipeline/       # Depth, geometry, inpainting, and scene packaging
|-- samples/        # Small, redistributable landscape inputs
|-- tests/          # Numeric and pipeline-boundary verification
|-- docs/           # Product and engineering documentation
`-- README.md
```

Directories will be added only when the first implementation is selected.

## Contributing

The project is early, but reproducible experiments, geometry improvements, and
translation corrections are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md)
before opening a pull request.

## License

DepthScape is licensed under the [MIT License](LICENSE).
