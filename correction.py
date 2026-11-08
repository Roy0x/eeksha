"""Auditable, deterministic human brush corrections for existing Eeksha labels."""
from __future__ import annotations

import hashlib
import io
import math
from PIL import Image, ImageDraw
import numpy as np

from eeksha import CLASSES
from review import load_annotation


def correct_mask(archive: bytes, strokes: list, reviewer: str) -> tuple[Image.Image, dict, dict]:
    original, metadata, qa = load_annotation(archive)
    if not isinstance(reviewer, str) or not 2 <= len(reviewer.strip()) <= 80:
        raise ValueError("Reviewer name or identifier must contain 2–80 characters")
    if not isinstance(strokes, list) or not 1 <= len(strokes) <= 1000:
        raise ValueError("Record between 1 and 1000 correction strokes")
    height, width = original.shape
    mask = Image.fromarray(original.astype(np.uint8), mode="L")
    draw = ImageDraw.Draw(mask)
    audit = []
    for index, stroke in enumerate(strokes, 1):
        if not isinstance(stroke, dict) or type(stroke.get("class_id")) is not int or stroke["class_id"] not in CLASSES:
            raise ValueError(f"Stroke {index}: invalid class ID")
        radius = stroke.get("radius")
        if type(radius) not in (int, float) or not math.isfinite(radius) or not 1 <= radius <= 100:
            raise ValueError(f"Stroke {index}: radius must be 1–100 image pixels")
        points = stroke.get("points")
        if not isinstance(points, list) or not 1 <= len(points) <= 4000:
            raise ValueError(f"Stroke {index}: invalid path length")
        clean = []
        for point in points:
            if (not isinstance(point, list) or len(point) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in point) or
                not (0 <= point[0] < width and 0 <= point[1] < height)):
                raise ValueError(f"Stroke {index}: point outside image")
            clean.append((round(point[0]), round(point[1])))
        label = stroke["class_id"]
        diameter = round(radius * 2)
        if len(clean) > 1:
            draw.line(clean, fill=label, width=max(1, diameter), joint="curve")
        for x, y in clean:
            draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=label)
        audit.append({"class_id": label, "radius": radius, "points": points})
    changed = int(np.count_nonzero(np.asarray(mask) != original))
    if changed == 0:
        raise ValueError("Corrections did not change any labeled pixels")
    provenance = {"provenance": "human_brush_correction", "review_status": "HUMAN_REVIEWED_NOT_GROUND_TRUTH",
                  "reviewer": reviewer.strip(), "original_annotation_sha256": hashlib.sha256(archive).hexdigest(),
                  "original_annotation_provenance": metadata["provenance"],
                  "original_label_sha256": qa["sources"]["labels"]["sha256"],
                  "image_width": width, "image_height": height,
                  "changed_pixels": changed, "strokes": audit,
                  "ground_truth_verified": False,
                  "limitations": ["Human corrections are not independently verified ground truth"]}
    return mask, provenance, qa


def verify_source(data: bytes, source: dict, name: str) -> None:
    if not data or hashlib.sha256(data).hexdigest() != source["sha256"]:
        raise ValueError(f"{name} SHA-256 does not match original annotation source")
