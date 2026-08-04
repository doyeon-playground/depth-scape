"""Safe local image ingestion for the depth baseline."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from .contracts import IngestedImage

DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_PIXELS = 40_000_000
_ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png"}
_MEDIA_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png"}
_FORMATS_BY_SUFFIX = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}
_EXIF_ORIENTATION_TAG = 274


class ImageValidationError(ValueError):
    """Raised when an input is unsafe or outside the supported image contract."""


def load_image(
    path: Path,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_pixels: int = DEFAULT_MAX_PIXELS,
) -> IngestedImage:
    """Validate and decode one JPG or PNG, applying its EXIF orientation.

    The returned image is RGB and uses the orientation a user sees in an
    orientation-aware photo viewer. Aspect ratio is never cropped or stretched.
    """

    source_path = path.expanduser().resolve()
    if not source_path.is_file():
        raise ImageValidationError(f"Input is not a readable file: {source_path}")
    if source_path.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise ImageValidationError(
            f"Unsupported extension for {source_path}; expected .jpg, .jpeg, or .png"
        )

    file_bytes = source_path.stat().st_size
    if file_bytes == 0:
        raise ImageValidationError(f"Input is empty: {source_path}")
    if file_bytes > max_file_bytes:
        raise ImageValidationError(f"Input exceeds the {max_file_bytes}-byte limit: {source_path}")

    try:
        source_bytes = source_path.read_bytes()
        if len(source_bytes) > max_file_bytes:
            raise ImageValidationError(
                f"Input changed while reading and exceeds the {max_file_bytes}-byte limit: "
                f"{source_path}"
            )
        with Image.open(BytesIO(source_bytes)) as opened:
            source_format = opened.format or ""
            if source_format not in _MEDIA_TYPES:
                raise ImageValidationError(
                    f"Unsupported encoded format {source_format!r}: {source_path}"
                )
            if source_format != _FORMATS_BY_SUFFIX[source_path.suffix.lower()]:
                raise ImageValidationError(
                    f"File extension and encoded format do not match: {source_path}"
                )

            original_width, original_height = opened.size
            pixels = original_width * original_height
            if original_width <= 0 or original_height <= 0 or pixels > max_pixels:
                raise ImageValidationError(
                    f"Input dimensions {original_width}x{original_height} exceed "
                    f"the {max_pixels}-pixel limit: {source_path}"
                )

            exif_orientation = int(opened.getexif().get(_EXIF_ORIENTATION_TAG, 1))
            icc_profile = opened.info.get("icc_profile")
            opened.load()
            normalized = ImageOps.exif_transpose(opened).convert("RGB")
            if icc_profile:
                try:
                    normalized = ImageCms.profileToProfile(
                        normalized,
                        ImageCms.ImageCmsProfile(BytesIO(icc_profile)),
                        ImageCms.createProfile("sRGB"),
                        outputMode="RGB",
                    )
                except (OSError, ImageCms.PyCMSError) as error:
                    raise ImageValidationError(
                        f"Could not convert embedded color profile to sRGB: {source_path}"
                    ) from error
                color_transform = "embedded-icc-to-srgb"
            else:
                color_transform = "untagged-assumed-srgb"
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise ImageValidationError(f"Could not decode image: {source_path}") from error

    return IngestedImage(
        image=normalized,
        source_path=source_path,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        media_type=_MEDIA_TYPES[source_format],
        source_format=source_format,
        original_width=original_width,
        original_height=original_height,
        exif_orientation=exif_orientation,
        orientation_applied=exif_orientation != 1,
        color_space="sRGB",
        color_transform=color_transform,
    )
