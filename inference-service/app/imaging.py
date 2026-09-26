"""Decode uploaded bytes into a PIL image. Supports PNG/JPEG and DICOM.

Only pixel data is read from DICOM files. Patient-identifying tags are never
touched here, and nothing in this module logs file contents or names.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_PIXELS = 100_000_000   # guards against decompression bombs

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class UnsupportedImage(ValueError):
    """The upload could not be decoded as a supported medical image."""


def _is_dicom(data: bytes) -> bool:
    return len(data) > 132 and data[128:132] == b"DICM"


def _to_uint8(arr: np.ndarray, center: float | None, width: float | None) -> np.ndarray:
    arr = arr.astype(np.float32)
    if center is not None and width is not None and width > 0:
        lo, hi = center - width / 2, center + width / 2
    else:
        lo, hi = np.percentile(arr, [0.5, 99.5])
    if hi <= lo:
        hi = lo + 1
    return (np.clip((arr - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)


def _first(value):
    """DICOM window tags may be a single number or a list; take the first."""
    if value is None:
        return None
    try:
        return float(value[0])
    except (TypeError, IndexError):
        return float(value)


def _decode_dicom(data: bytes) -> Image.Image:
    import pydicom

    try:
        ds = pydicom.dcmread(io.BytesIO(data))
        arr = ds.pixel_array
    except Exception as exc:   # pydicom raises many types for bad/compressed data
        raise UnsupportedImage(
            "Could not read DICOM pixel data (corrupt file or unsupported compression)"
        ) from exc

    if arr.ndim == 3 and getattr(ds, "SamplesPerPixel", 1) == 1:
        arr = arr[0]                      # multi-frame: use the first frame
    if arr.ndim == 3:                     # colour DICOM (photographs, endoscopy, slide tiles)
        pi = str(getattr(ds, "PhotometricInterpretation", "RGB"))
        if pi.startswith("YBR"):
            from pydicom.pixels import convert_color_space
            arr = convert_color_space(arr, pi, "RGB")
        return Image.fromarray(arr.astype(np.uint8)).convert("RGB")

    slope = float(getattr(ds, "RescaleSlope", 1) or 1)
    intercept = float(getattr(ds, "RescaleIntercept", 0) or 0)
    arr = arr.astype(np.float32) * slope + intercept
    img8 = _to_uint8(arr, _first(getattr(ds, "WindowCenter", None)),
                     _first(getattr(ds, "WindowWidth", None)))
    if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
        img8 = 255 - img8                 # MONOCHROME1 stores inverted intensities
    return Image.fromarray(img8).convert("RGB")


def decode_image(data: bytes) -> Image.Image:
    """Return an RGB PIL image. Colour is preserved (it is diagnostic in dermatology,
    fundus photography, endoscopy and pathology); grayscale sources come back with the
    gray value replicated across channels. Models that expect grayscale convert it."""
    if not data:
        raise UnsupportedImage("Empty upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UnsupportedImage("File too large")
    if _is_dicom(data):
        return _decode_dicom(data)
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise UnsupportedImage("Unsupported or corrupt image file") from exc
    if img.mode in ("L", "I", "I;16", "F", "1", "LA"):
        return img.convert("L").convert("RGB")
    return img.convert("RGB")


def is_grayscale(image: Image.Image) -> bool:
    arr = np.asarray(image.convert("RGB"))
    return bool((arr[..., 0] == arr[..., 1]).all() and (arr[..., 1] == arr[..., 2]).all())
