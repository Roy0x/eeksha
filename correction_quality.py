"""Quantitative before/after evidence for a human-corrected semantic mask."""
from __future__ import annotations

import numpy as np
from PIL import Image

from eeksha import CLASSES


def head_regions(head: np.ndarray, valid: np.ndarray, *, minimum_pixels: int = 25) -> dict:
    """Find 8-connected head-mask regions; these are not verified plant instances."""
    height, width = head.shape
    seen = np.zeros(head.shape, dtype=bool)
    regions = []
    for y, x in np.argwhere(head):
        y, x = int(y), int(x)
        if seen[y, x]:
            continue
        seen[y, x] = True
        pending = [(y, x)]
        count = with_depth = 0
        min_x = max_x = x
        min_y = max_y = y
        while pending:
            cy, cx = pending.pop()
            count += 1
            with_depth += int(valid[cy, cx])
            min_x, max_x = min(min_x, cx), max(max_x, cx)
            min_y, max_y = min(min_y, cy), max(max_y, cy)
            for ny in range(max(0, cy - 1), min(height, cy + 2)):
                for nx in range(max(0, cx - 1), min(width, cx + 2)):
                    if head[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        pending.append((ny, nx))
        if count < minimum_pixels:
            continue
        coverage = with_depth / count
        flags = []
        if coverage < 0.25:
            flags.append("LOW_VALID_DEPTH_COVERAGE")
        if min_x == 0 or min_y == 0 or max_x == width - 1 or max_y == height - 1:
            flags.append("TOUCHES_IMAGE_BORDER")
        regions.append({"pixels": count, "valid_3d_points": with_depth,
                        "valid_depth_fraction": round(coverage, 6),
                        "bounding_box_xyxy": [min_x, min_y, max_x, max_y],
                        "flags": flags})
    regions.sort(key=lambda item: item["pixels"], reverse=True)
    for index, region in enumerate(regions, 1):
        region["region_id"] = index
    return {"connectivity": 8, "minimum_pixels": minimum_pixels,
            "significant_region_count": len(regions), "regions": regions[:30],
            "omitted_regions": max(0, len(regions) - 30),
            "warning": "Connected pixel regions are not independently verified broccoli instances."}


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
        "broccoli_head_regions": head_regions(after == 4, valid),
        "warning": "Pixel counts and depth presence measure coverage, not semantic accuracy or metric 3D accuracy.",
    }
