"""Auditable, deterministic human brush corrections for existing Eeksha labels."""
from __future__ import annotations

import hashlib
import io
import math
import json
import zipfile
from PIL import Image, ImageDraw
import numpy as np

from eeksha import CLASSES
from review import load_annotation


def correct_mask(archive: bytes, strokes: list, reviewer: str) -> tuple[Image.Image, dict, dict]:
    original, metadata, qa = load_annotation(archive)
    mask, provenance = apply_strokes(original, strokes, reviewer)
    provenance.update({"provenance": "human_brush_correction",
                       "review_status": "HUMAN_REVIEWED_NOT_GROUND_TRUTH",
                       "original_annotation_sha256": hashlib.sha256(archive).hexdigest(),
                       "original_annotation_provenance": metadata["provenance"],
                       "original_label_sha256": qa["sources"]["labels"]["sha256"]})
    return mask, provenance, qa


def apply_strokes(original: np.ndarray, strokes: list, reviewer: str) -> tuple[Image.Image, dict]:
    """Replay human brush actions over an explicit starting mask (including all-unknown)."""
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
    provenance = {"provenance": "human_brush_annotation", "review_status": "UNREVIEWED",
                  "reviewer": reviewer.strip(),
                  "image_width": width, "image_height": height,
                  "changed_pixels": changed, "strokes": audit,
                  "ground_truth_verified": False,
                  "limitations": ["Human brush labels are not independently reviewed ground truth"]}
    return mask, provenance


def verify_source(data: bytes, source: dict, name: str) -> None:
    if not data or hashlib.sha256(data).hexdigest() != source["sha256"]:
        raise ValueError(f"{name} SHA-256 does not match original annotation source")


def load_exported_mask(archive_bytes: bytes) -> tuple[np.ndarray, dict]:
    """Load polygon or brush-export labels, requiring matching recorded mask hash."""
    if not archive_bytes or len(archive_bytes) > 30 * 1024 * 1024:
        raise ValueError("Eeksha dataset ZIP must be under 30 MB")
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            members = archive.infolist()
            names = [item.filename for item in members]
            if len(names) != len(set(names)) or not {'labels.png', 'qa_report.json'} <= set(names):
                raise ValueError("Missing or duplicate required ZIP entries")
            if len(members) > 32 or sum(item.file_size for item in members) > 50 * 1024 * 1024:
                raise ValueError("Dataset ZIP exceeds extraction limits")
            labels_data = archive.read('labels.png')
            report = json.loads(archive.read('qa_report.json'))
            if 'annotations.json' in names:
                labels, _, _ = load_annotation(archive_bytes)
            else:
                with Image.open(io.BytesIO(labels_data)) as im:
                    if im.mode not in ('L', 'P') or im.width * im.height > 4_000_000:
                        raise ValueError('Unsupported label mask')
                    labels = np.asarray(im).copy()
                if not np.isin(labels, list(CLASSES)).all():
                    raise ValueError('Unexpected semantic class IDs')
    except (zipfile.BadZipFile, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid Eeksha dataset ZIP') from exc
    sources = report.get('sources') if isinstance(report, dict) else None
    if not isinstance(sources, dict) or sources.get('labels', {}).get('sha256') != hashlib.sha256(labels_data).hexdigest():
        raise ValueError('Label mask does not match QA SHA-256')
    for key in ('rgb', 'depth'):
        if not isinstance(sources.get(key, {}).get('sha256'), str):
            raise ValueError(f'Missing {key} source hash')
    if not isinstance(report.get('calibration'), dict):
        raise ValueError('Missing calibration metadata')
    return labels, report
