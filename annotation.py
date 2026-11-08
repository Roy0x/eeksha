"""Explicit human polygon annotations rasterized into image-aligned class masks."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from eeksha import CLASSES


def build_mask(width: int, height: int, polygons: list) -> Image.Image:
    if not 1 <= width <= 10000 or not 1 <= height <= 10000:
        raise ValueError("Invalid image size")
    if not isinstance(polygons, list) or not 1 <= len(polygons) <= 200:
        raise ValueError("Submit between 1 and 200 polygons")
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for n, item in enumerate(polygons, 1):
        if not isinstance(item, dict) or type(item.get("class_id")) is not int:
            raise ValueError(f"Polygon {n}: invalid class ID")
        label = item["class_id"]
        if label not in CLASSES or label == 0:
            raise ValueError(f"Polygon {n}: select a non-unknown semantic class")
        vertices = item.get("vertices")
        if not isinstance(vertices, list) or not 3 <= len(vertices) <= 500:
            raise ValueError(f"Polygon {n}: requires 3–500 vertices")
        points = []
        for point in vertices:
            if (not isinstance(point, list) or len(point) != 2 or
                    any(type(v) not in (int, float) or not math.isfinite(v) for v in point)):
                raise ValueError(f"Polygon {n}: invalid vertex")
            x, y = point
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError(f"Polygon {n}: vertex outside image")
            points.append((round(x), round(y)))
        if len(set(points)) < 3:
            raise ValueError(f"Polygon {n}: degenerate geometry")
        draw.polygon(points, fill=label)
    return mask


def record_annotations(folder: Path, polygons: list, width: int, height: int) -> dict:
    mask = build_mask(width, height, polygons)
    mask.save(folder / "labels.png")
    counts = np.bincount(np.asarray(mask).ravel(), minlength=max(CLASSES) + 1)
    document = {"provenance": "human_drawn_polygon_annotations", "review_status": "UNREVIEWED",
                "image_width": width, "image_height": height,
                "polygons": polygons,
                "pixel_counts": {CLASSES[i]: int(counts[i]) for i in CLASSES},
                "limitations": ["Manual polygons, not independently verified ground truth",
                                "Unannotated pixels remain unknown; drawn polygons can overlap"]}
    (folder / "annotations.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    return document
