"""Create a small deterministic landscape fixture for local or Colab demos."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def create_demo_landscape(path: Path, *, width: int = 640, height: int = 384) -> None:
    """Write an original synthetic landscape as an RGB PNG.

    The generated image is project-authored test material covered by the
    repository's MIT license. It intentionally includes sky, mountain edges,
    water, and a thin foreground tree.
    """

    if width < 64 or height < 64:
        raise ValueError("Demo dimensions must both be at least 64 pixels")

    image = Image.new("RGB", (width, height))
    pixels = image.load()
    horizon = int(height * 0.62)
    for y in range(height):
        if y < horizon:
            blend = y / max(horizon - 1, 1)
            color = (
                int(92 + 86 * blend),
                int(158 + 55 * blend),
                int(218 + 25 * blend),
            )
        else:
            blend = (y - horizon) / max(height - horizon - 1, 1)
            color = (
                int(54 - 22 * blend),
                int(126 - 38 * blend),
                int(154 - 42 * blend),
            )
        for x in range(width):
            pixels[x, y] = color

    draw = ImageDraw.Draw(image)
    draw.polygon(
        [
            (0, horizon),
            (int(width * 0.20), int(height * 0.37)),
            (int(width * 0.38), horizon),
        ],
        fill=(84, 111, 121),
    )
    draw.polygon(
        [
            (int(width * 0.18), horizon),
            (int(width * 0.55), int(height * 0.24)),
            (int(width * 0.83), horizon),
        ],
        fill=(68, 91, 103),
    )
    draw.polygon(
        [
            (int(width * 0.52), int(height * 0.25)),
            (int(width * 0.60), int(height * 0.35)),
            (int(width * 0.55), int(height * 0.32)),
            (int(width * 0.49), int(height * 0.37)),
        ],
        fill=(224, 229, 224),
    )
    draw.rectangle(
        (
            int(width * 0.08),
            int(height * 0.48),
            int(width * 0.10),
            int(height * 0.90),
        ),
        fill=(55, 44, 31),
    )
    tree_x = int(width * 0.09)
    tree_y = int(height * 0.49)
    radius = int(min(width, height) * 0.09)
    draw.ellipse(
        (tree_x - radius, tree_y - radius, tree_x + radius, tree_y + radius),
        fill=(35, 83, 57),
    )
    draw.polygon(
        [
            (0, height),
            (0, int(height * 0.84)),
            (int(width * 0.33), int(height * 0.88)),
            (int(width * 0.62), int(height * 0.82)),
            (width, int(height * 0.87)),
            (width, height),
        ],
        fill=(48, 92, 54),
    )

    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=384)
    args = parser.parse_args()
    create_demo_landscape(args.output, width=args.width, height=args.height)
    print(args.output.expanduser().resolve())


if __name__ == "__main__":
    main()
