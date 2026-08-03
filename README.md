# ScenePort

**Turn scenes into spaces.**

ScenePort is an open-source project for transforming photos, videos, and live
camera feeds into explorable 3D environments. Development starts with a
single-image prototype and expands toward multi-view video reconstruction and
live camera capture.

> [!IMPORTANT]
> A single image cannot reveal geometry that was never captured. The first
> milestone produces an inferred, depth-aware 3D scene rather than a complete
> or metrically accurate reconstruction.

## Languages

English is the source language for the project and its documentation.

- [한국어](docs/i18n/README.ko.md)
- [日本語](docs/i18n/README.ja.md)
- [简体中文](docs/i18n/README.zh-CN.md)
- [Español](docs/i18n/README.es.md)

## Vision

ScenePort aims to make spatial capture approachable:

1. Start with a photo and generate an interactive depth-aware scene.
2. Use video frames to reconstruct more complete and consistent geometry.
3. Connect a camera for near-real-time spatial capture and visualization.

## First MVP: Photo to 3D

The first milestone will:

- accept a JPG or PNG image;
- estimate a depth map from the image;
- convert image pixels and estimated depth into colored 3D geometry;
- display the result in an interactive viewer with orbit, pan, and zoom; and
- make the reconstruction limits visible to the user.

The initial milestone does not promise hidden-surface reconstruction,
real-world scale, production-grade geometry, or real-time processing.

## Project status

ScenePort is currently in the **planning and prototyping** stage. APIs,
formats, and implementation details may change without notice.

## Documentation

- [Product brief](docs/product-brief.md)
- [Roadmap](docs/roadmap.md)
- [Architecture](docs/architecture.md)
- [Internationalization](docs/i18n.md)
- [Contributing](CONTRIBUTING.md)

## Planned repository structure

```text
scene-port/
|-- frontend/       # Upload flow and interactive 3D viewer
|-- backend/        # API and job orchestration
|-- pipeline/       # Depth estimation and 3D reconstruction
|-- samples/        # Small, redistributable test inputs
|-- docs/           # Product and engineering documentation
`-- README.md
```

Directories will be added only when the first implementation is selected.

## Contributing

The project is early, but design discussions, reproducible experiments, and
translation improvements are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md)
before opening a pull request.

## License

ScenePort is licensed under the [MIT License](LICENSE).
