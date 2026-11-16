"""Read-only preflight checks for aligned Eeksha RGB-D scene inputs.

Checks structural consistency only, not calibration truth or semantic accuracy.
"""
from __future__ import annotations

import io
import json
import math

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_PIXELS = 4_000_000
SUPPORTED_CLASSES = set(range(6))


def inspect_inputs(rgb_bytes: bytes, depth_bytes: bytes, label_bytes: bytes,
                   calibration_bytes: bytes) -> dict:
    if not all((rgb_bytes, depth_bytes, label_bytes, calibration_bytes)):
        raise ValueError("RGB, depth, labels and calibration must all be supplied")

    dimensions = {}
    for name, data in (("RGB", rgb_bytes), ("Depth", depth_bytes), ("Labels", label_bytes)):
        try:
            with Image.open(io.BytesIO(data)) as img:
                if img.format != "PNG":
                    raise ValueError(f"{name} must be a PNG image")
                if img.width * img.height > MAX_IMAGE_PIXELS:
                    raise ValueError(f"{name} exceeds the 4-million-pixel input limit")
                dimensions[name] = img.size
                if name == "RGB" and img.mode not in ("RGB", "RGBA"):
                    raise ValueError("RGB must use RGB or RGBA pixels")
                if name == "Depth" and img.mode not in ("I;16", "I;16L", "I;16B", "I", "F"):
                    raise ValueError("Depth must be a single-channel numeric PNG (16-bit, 32-bit, or float)")
                if name == "Labels":
                    if img.mode not in ("L", "I;16", "I;16L", "I;16B", "I"):
                        raise ValueError("Labels must be a single-channel integer class-ID PNG")
                    values = set(img.getdata())
                    if not values.issubset(SUPPORTED_CLASSES):
                        raise ValueError("Labels contain unsupported class IDs; supported values are 0–5")
        except (OSError, UnidentifiedImageError) as error:
            raise ValueError(f"{name} is not a readable PNG image") from error

    if len(set(dimensions.values())) != 1:
        raise ValueError("RGB, depth and labels have mismatched dimensions; use aligned images")

    try:
        config = json.loads(calibration_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Calibration must be valid UTF-8 JSON") from error
    if not isinstance(config, dict):
        raise ValueError("Calibration must be a JSON object")

    for key in ("fx", "fy", "cx", "cy", "depth_scale"):
        value = config.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Missing or invalid calibration parameter: {key}")
    if config["fx"] <= 0 or config["fy"] <= 0 or config["depth_scale"] <= 0:
        raise ValueError("Focal lengths and depth_scale must be positive")
    if config.get("depth_type") not in ("axial_z", "ray_distance"):
        raise ValueError("depth_type must explicitly be axial_z or ray_distance")
    width, height = dimensions["RGB"]
    if config.get("width", width) != width or config.get("height", height) != height:
        raise ValueError("Recorded calibration dimensions do not match input images")

    return {
        "ready": True,
        "width": width,
        "height": height,
        "depth_type": config["depth_type"],
        "status": "STRUCTURAL_INPUT_CHECK_ONLY",
        "warnings": [
            "Camera intrinsics and RGB-depth registration were not independently verified",
            "Class labels were not independently validated against real-world observations",
            "Passing preflight does not imply robot safety or geometric accuracy",
        ],
    }
