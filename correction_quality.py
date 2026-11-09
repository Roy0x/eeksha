"""Quantitative before/after evidence for a human-corrected semantic mask."""
from __future__ import annotations

import numpy as np
from PIL import Image

from eeksha import CLASSES


def summarize_correction(original: np.ndarray, corrected: Image.Image,
                         depth: np.ndarray, scale: float, max_depth_m: float) -> dict:
    after = np.asarray(corrected)
    if original.shape != after.shape or depth.shape != after.shape:
        raise ValueError("Correction QA image/depth dimensions differ")
    if not np.issubdtype(depth.dtype, np.number) or not np.isfinite(scale) or scale <= 0:
        raise ValueError("Correction QA requires numeric depth and a positive scale")
    measured = depth.astype(np.float64) * scale
    valid = np.isfinite(measured) & (measured > 0) & (measured <= max_depth_m)
    changed = original != after
    classes = {}
    for class_id, name in CLASSES.items():
        before_pixels = original == class_id
        after_pixels = after == class_id
        after_count = int(after_pixels.sum())
        valid_after = int(np.count_nonzero(after_pixels & valid))
        classes[name] = {
            "before_pixels": int(before_pixels.sum()),
            "after_pixels": after_count,
            "before_valid_3d_points": int(np.count_nonzero(before_pixels & valid)),
            "after_valid_3d_points": valid_after,
            "after_valid_depth_fraction": round(valid_after / after_count, 6) if after_count else None,
        }
    changed_count = int(changed.sum())
    with_depth = int(np.count_nonzero(changed & valid))
    return {
        "status": "HUMAN_REVIEW_REQUIRED",
        "ground_truth_verified": False,
        "total_pixels": int(after.size),
        "changed_pixels": changed_count,
        "changed_pixels_with_valid_depth": with_depth,
        "changed_pixels_without_valid_depth": changed_count - with_depth,
        "total_valid_depth_pixels": int(valid.sum()),
        "classes": classes,
        "warning": "Pixel counts and depth presence measure coverage, not semantic accuracy or metric 3D accuracy.",
    }
