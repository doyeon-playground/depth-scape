from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageCms

from depth_scape.image_io import ImageValidationError, load_image


class ImageIngestionTests(unittest.TestCase):
    def test_loads_png_as_rgb_without_changing_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "landscape.png"
            Image.new("RGBA", (8, 4), (10, 20, 30, 128)).save(path)

            loaded = load_image(path, max_pixels=32)

            self.assertEqual(loaded.image.mode, "RGB")
            self.assertEqual((loaded.width, loaded.height), (8, 4))
            self.assertEqual(loaded.media_type, "image/png")
            self.assertFalse(loaded.orientation_applied)
            self.assertEqual(loaded.color_space, "sRGB")
            self.assertEqual(loaded.color_transform, "untagged-assumed-srgb")
            self.assertEqual(len(loaded.source_sha256), 64)

    def test_converts_an_embedded_icc_profile_to_srgb(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiled.png"
            profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            Image.new("RGB", (4, 3), (10, 20, 30)).save(path, icc_profile=profile)

            loaded = load_image(path)

            self.assertEqual(loaded.image.mode, "RGB")
            self.assertEqual(loaded.color_space, "sRGB")
            self.assertEqual(loaded.color_transform, "embedded-icc-to-srgb")

    def test_applies_exif_orientation_before_inference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rotated.jpg"
            exif = Image.Exif()
            exif[274] = 6
            Image.new("RGB", (2, 3), (10, 20, 30)).save(path, exif=exif)

            loaded = load_image(path)

            self.assertEqual((loaded.original_width, loaded.original_height), (2, 3))
            self.assertEqual((loaded.width, loaded.height), (3, 2))
            self.assertEqual(loaded.exif_orientation, 6)
            self.assertTrue(loaded.orientation_applied)

    def test_rejects_size_format_and_extension_contract_violations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            oversized = root / "oversized.png"
            Image.new("RGB", (5, 5)).save(oversized)
            with self.assertRaises(ImageValidationError):
                load_image(oversized, max_pixels=24)

            mismatched = root / "mismatched.jpg"
            Image.new("RGB", (2, 2)).save(mismatched, format="PNG")
            with self.assertRaises(ImageValidationError):
                load_image(mismatched)

            unsupported = root / "landscape.webp"
            Image.new("RGB", (2, 2)).save(unsupported)
            with self.assertRaises(ImageValidationError):
                load_image(unsupported)


if __name__ == "__main__":
    unittest.main()
