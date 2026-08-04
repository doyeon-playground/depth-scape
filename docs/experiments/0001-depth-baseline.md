# 0001: Depth Anything V2 Small baseline

- **Status:** Implementation ready; Colab measurement pending
- **Date:** 2026-08-04
- **Owner:** DepthScape

## Question

Can a small, redistributable monocular model produce a pixel-aligned relative
depth artifact from one landscape JPG or PNG through a workflow that is safe to
repeat locally or in a fresh Colab runtime?

This experiment does not test metric accuracy, scene layers, inpainting, or
camera motion.

## Pinned baseline

| Item | Recorded value |
| --- | --- |
| Model | `depth-anything/Depth-Anything-V2-Small-hf` |
| Model revision | `5426e4f0f36572d16453bbda7a8389317b1bef99` |
| Weight file | `model.safetensors` |
| Weight SHA-256 | `3152477ce0d8d6978d76b995120de97cb5b928701fd0f817769f59e249a16b70` |
| Weight size | 99,173,660 bytes |
| Parameters | 24.8 million |
| Backend | Hugging Face Transformers 4.56.0 |
| Upstream model code license | Apache-2.0 |
| Small checkpoint weight license | Apache-2.0 |
| Transformers backend code license | Apache-2.0 |
| Depth type | Unitless relative proximity; larger is nearer |

The [official Depth Anything V2 repository](https://github.com/DepthAnything/Depth-Anything-V2)
lists the Small checkpoint as Apache-2.0 and the Base, Large, and Giant variants
as CC-BY-NC-4.0. The
[official checkpoint card](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf)
also identifies the Small Transformers checkpoint as Apache-2.0. The adapter
follows the [Transformers Depth Anything V2 API](https://huggingface.co/docs/transformers/v4.56.0/en/model_doc/depth_anything_v2).

The upstream authors note that their OpenCV/native implementation and the
Transformers/Pillow path can differ slightly during upsampling. DepthScape uses
the Transformers path for a small replaceable adapter and pinned checkpoint,
not to reproduce upstream benchmark numbers exactly.

## Reproduction

Supported model runtime: Python 3.10 through 3.13. A CUDA runtime is recommended,
but CPU is an explicit slower fallback. PyTorch is constrained to a compatible
major range because Colab supplies accelerator-specific wheels; every run stores
the exact installed PyTorch and package versions in `run.json`.

```bash
python -m pip install -e ".[depth]"
python samples/create_demo_landscape.py demo-landscape.png
depth-scape-depth demo-landscape.png --output-dir runs/demo
```

The project-authored sample generator creates a deterministic 640x384 PNG with
sky, mountain edges, water, and a thin foreground tree. It avoids committing
user media or an opaque binary fixture. The
[Colab notebook](../../notebooks/0001_depth_baseline.ipynb) performs the same
steps and prints the checked-out DepthScape revision. Colab is a remote runtime;
photos uploaded there are not local-only and should not contain sensitive data.

If the repository is private, store a fine-grained, read-only GitHub token in
Colab Secrets under `GITHUB_TOKEN`. The notebook passes it to Git only through a
temporary process environment; never paste a token into a notebook cell or
commit one to the repository. No token is needed after the repository becomes
public.

The first model run downloads the pinned 99.2 MB checkpoint from Hugging Face.
Use `--offline` after it is cached to reject hidden network access. Other useful
controls are `--device`, `--precision`, `--seed`, `--max-file-mib`,
`--max-megapixels`, and the explicit `--overwrite` switch.

## Input contract

- One file whose extension and encoded format agree: JPG, JPEG, or PNG.
- Default maximum encoded size: 50 MiB.
- Default maximum decoded dimensions: 40 million pixels.
- EXIF orientation is applied before inference and recorded.
- Embedded ICC profiles are converted to sRGB; untagged images are explicitly
  treated as sRGB and the assumption is recorded.
- The normalized RGB image is never cropped or stretched.
- The source SHA-256 is recorded, but image bytes and absolute paths are not
  copied into the manifest.

## Output contract

All artifacts share the normalized image dimensions and use row-major
`(height, width)` arrays with a top-left origin, x right, and y down.

| File | Contract | Provenance |
| --- | --- | --- |
| `relative-depth.npy` | float32, HxW, `[0, 1]`, larger is nearer | Inferred from observed RGB |
| `depth-preview.png` | uint8 grayscale, white near, display only | Visualization of inferred depth |
| `run.json` | schema `0.1`, model, transform, runtime, performance, warnings | Run metadata |

The NPY file contains no metric units. Per-pixel arrays are binary artifacts,
not JSON fields. The source RGB is observed; every depth value is inferred. No
hidden RGB content is generated in this experiment.

## Reproducibility and measurement

- The model repository and weights are pinned by immutable revision and digest.
- Transformers is pinned to 4.56.0; actual Python, PyTorch, Pillow, NumPy, and
  Safetensors versions are recorded per run.
- The default seed is `0` and deterministic PyTorch algorithms are requested.
- `run.json` records the DepthScape Git revision and dirty state, device,
  precision, model-load time, inference time, device name, and peak CUDA memory
  when CUDA is used.
- CPU and MPS do not currently expose a comparable peak-memory measurement, so
  the field is `null` with a warning on those paths.

Do not compare runtime values unless input dimensions, device, precision,
warm-up state, package versions, and checkpoint revision match. The first run
includes model loading and may include a network download; inference time is
recorded separately.

## Verification performed

The model-independent contract suite runs without downloading weights:

```text
python -m unittest discover -s tests -v
8 tests passed
```

It covers JPG/PNG decoding, EXIF rotation, ICC-to-sRGB conversion, dimension and
format validation, float depth normalization, invalid shape/range rejection,
preview semantics, pixel alignment, provenance fields, and overwrite protection.

A local CPU smoke run also completed on the project-authored 640x384 sample:

| Item | Observed value |
| --- | --- |
| OS | Windows 11 |
| Python | 3.12.13 |
| PyTorch | 2.13.0 |
| Transformers | 4.56.0 |
| NumPy / Pillow / Safetensors | 2.5.1 / 12.3.0 / 0.8.0 |
| Device / precision | CPU / float32 |
| Model load | 23.177 seconds, including the first checkpoint download |
| First inference, no warm-up | 0.255 seconds |
| Output shape | 384x640, aligned with the input |
| Raw model range | -0.598777 to 4.787487 |

This smoke value confirms the CPU path and artifact writer, not representative
performance. CPU peak memory was unavailable and correctly recorded as `null`.
A second cached `--offline` run produced the same normalized NPY SHA-256,
`7a25a412fe31d77ff8c7d533f726f008091ce74b5663131715e8ddb51fa627ed`,
on this environment. That is a same-environment check, not a promise of
bit-identical output across devices or package versions.

An actual Colab GPU runtime and peak-memory result have not yet been recorded.
This document must remain in **measurement pending** status until a fresh Colab
run attaches its `run.json` values and qualitative observations. No performance
or landscape-quality claim is made yet.

## Failure set for the next run

Evaluate at least one clearly licensed or project-authored image in each group:

- uniform or overexposed sky;
- thin branches, fencing, or wires;
- distant mountains with haze;
- reflective or textureless water;
- low-contrast foreground/background boundaries;
- a strong foreground occluder; and
- an extreme landscape aspect ratio.

Record edge halos, incorrect near/far ordering, unstable flat regions, and lost
thin structures. These observations decide whether the adapter is adopted or a
different baseline is required.

## Current decision

Keep Depth Anything V2 Small as the provisional Phase 1 baseline because its
small checkpoint has an official permissive license and a maintained
Transformers integration. Do not promote it to a fixed product dependency until
the pending Colab measurement and landscape failure-set review are complete.
