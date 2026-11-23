"""Transparent dataset coverage diagnostics; never interpreted as label accuracy."""
from __future__ import annotations

import numpy as np


def summarize_coverage(depth: np.ndarray, labels: np.ndarray, scale: float, max_depth_m: float) -> dict:
    if depth.shape != labels.shape or depth.ndim != 2:
        raise ValueError("Depth and semantic mask dimensions differ")
    measured = depth.astype(np.float64) * scale
    finite = np.isfinite(measured)
    zero_or_negative = finite & (measured <= 0)
    too_far = finite & (measured > max_depth_m)
    invalid_numeric = ~finite
    valid = finite & (measured > 0) & (measured <= max_depth_m)
    labeled = labels != 0
    total = int(depth.size)
    valid_count = int(np.count_nonzero(valid))
    labeled_count = int(np.count_nonzero(labeled))
    labeled_valid = int(np.count_nonzero(valid & labeled))
    unknown_valid = valid_count - labeled_valid
    flags = []
    if valid_count < total * 0.5:
        flags.append("LOW_DEPTH_COVERAGE_UNDER_50_PERCENT")
    if valid_count and labeled_valid < valid_count * 0.5:
        flags.append("LOW_SEMANTIC_COVERAGE_UNDER_50_PERCENT_OF_VALID_DEPTH")
    return {
        "total_image_pixels": total,
        "valid_depth_pixels": valid_count,
        "missing_or_nonpositive_depth_pixels": int(np.count_nonzero(zero_or_negative)),
        "over_max_depth_pixels": int(np.count_nonzero(too_far)),
        "nonfinite_depth_pixels": int(np.count_nonzero(invalid_numeric)),
        "labeled_image_pixels": labeled_count,
        "labeled_valid_depth_points": labeled_valid,
        "unknown_valid_depth_points": unknown_valid,
        "labeled_image_fraction": round(labeled_count / total, 6) if total else 0.0,
        "labeled_valid_depth_fraction": round(labeled_valid / valid_count, 6) if valid_count else 0.0,
        "unknown_valid_depth_fraction": round(unknown_valid / valid_count, 6) if valid_count else 0.0,
        "flags": flags,
        "warning": "Coverage describes data availability, not semantic correctness or geometric accuracy.",
    }
