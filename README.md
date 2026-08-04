# DepthScape

**Turn a landscape photo into an explorable 2.5D scene.**

DepthScape is an open-source project that transforms one landscape photo into a
layered, depth-aware scene. It estimates relative depth, separates the image
into foreground, midground, and background layers, fills small regions hidden
behind foreground objects, and renders a controlled parallax view in the
browser.

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
    -> foreground, midground, and background layers
    -> occlusion and hole masks
    -> background image and depth completion
    -> layered 2.5D scene
    -> limited interactive parallax view
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
- preview relative depth and layer masks;
- generate only the background regions needed for the allowed camera motion;
- distinguish observed pixels from generated pixels;
- render a keyboard-accessible, limited parallax view; and
- retain enough configuration metadata to reproduce the result.

Video reconstruction, live camera capture, unrestricted camera movement,
metric depth, and full hidden-surface reconstruction are outside the project
scope.

## Project status

DepthScape is currently in the **planning and baseline-evaluation** stage. APIs,
artifact formats, model choices, and implementation details may change as the
first experiments are completed.

## Documentation

- [Product brief](docs/product-brief.md)
- [Roadmap](docs/roadmap.md)
- [Architecture](docs/architecture.md)
- [Model baselines](docs/model-baselines.md)
- [Scope decision](docs/decisions/0001-focus-on-landscape-2-5d.md)
- [Internationalization](docs/i18n.md)
- [Contributing](CONTRIBUTING.md)

## Planned repository structure

```text
depth-scape/
|-- frontend/       # Image workflow and limited-parallax viewer
|-- pipeline/       # Depth, layers, inpainting, and scene packaging
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
