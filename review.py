"""Compare two Eeksha human annotation exports without declaring truth."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile

import numpy as np
from PIL import Image

from annotation import build_mask
from eeksha import CLASSES

REQUIRED = {"annotations.json", "labels.png", "qa_report.json"}
MAX_ARCHIVE_BYTES = 30 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


def load_annotation(data: bytes) -> tuple[np.ndarray, dict, dict]:
    if not data or len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("Annotation ZIP is empty or exceeds 30 MB")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or not REQUIRED.issubset(names):
                raise ValueError("Missing or duplicate required ZIP entries")
            if sum(item.file_size for item in archive.infolist()) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("ZIP uncompressed size exceeds 50 MB")
            metadata = json.loads(archive.read("annotations.json"))
            report = json.loads(archive.read("qa_report.json"))
            mask_data = archive.read("labels.png")
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid Eeksha annotation ZIP") from exc
    if not isinstance(metadata, dict) or metadata.get("provenance") != "human_drawn_polygon_annotations":
        raise ValueError("Missing human-drawn annotation provenance")
    if metadata.get("review_status") != "UNREVIEWED":
        raise ValueError("Unexpected annotation review status")
    with Image.open(io.BytesIO(mask_data)) as image:
        if image.mode not in ("L", "P"):
            raise ValueError("Label mask must use integer class IDs")
        if image.width > 4096 or image.height > 4096 or image.width * image.height > 4_000_000:
            raise ValueError("Annotation mask is too large for the local review tool")
        mask = np.asarray(image).copy()
    if not np.isin(mask, list(CLASSES)).all():
        raise ValueError("Unexpected class IDs in mask")
    if mask.shape != (metadata.get("image_height"), metadata.get("image_width")):
        raise ValueError("Mask dimensions disagree with annotation metadata")
    if not np.array_equal(mask, np.asarray(build_mask(mask.shape[1], mask.shape[0], metadata.get("polygons")))):
        raise ValueError("Mask does not match recorded polygons")
    sources = report.get("sources") if isinstance(report, dict) else None
    if not isinstance(sources, dict) or sources.get("labels", {}).get("sha256") != hashlib.sha256(mask_data).hexdigest():
        raise ValueError("Mask SHA-256 disagrees with original QA provenance")
    for key in ("rgb", "depth"):
        if not isinstance(sources.get(key, {}).get("sha256"), str):
            raise ValueError(f"Missing source {key} SHA-256")
    return mask, metadata, report


def compare_exports(first: bytes, second: bytes) -> tuple[dict, bytes]:
    a, ma, qa = load_annotation(first)
    b, mb, qb = load_annotation(second)
    if a.shape != b.shape:
        raise ValueError("Annotation image sizes differ")
    for key in ("rgb", "depth"):
        if qa["sources"][key]["sha256"] != qb["sources"][key]["sha256"]:
            raise ValueError(f"Annotations refer to different {key.upper()} sources")
    if qa["calibration"] != qb["calibration"]:
        raise ValueError("Calibration differs between exports")
    metrics = {}
    for class_id, class_name in CLASSES.items():
        if class_id == 0:
            continue
        aa, bb = a == class_id, b == class_id
        intersection = int(np.count_nonzero(aa & bb))
        union = int(np.count_nonzero(aa | bb))
        metrics[class_name] = {"mask_a_pixels": int(aa.sum()), "mask_b_pixels": int(bb.sum()),
                               "intersection_pixels": intersection, "union_pixels": union,
                               "iou": round(intersection / union, 6) if union else None}
    either = (a != 0) | (b != 0)
    both_same = (a != 0) & (a == b)
    union_count = int(either.sum())
    agreement = int(both_same.sum())
    mismatch = either & ~both_same
    preview = np.zeros((*a.shape, 3), dtype=np.uint8)
    preview[(a != 0) & (b == 0)] = [255, 70, 190]  # only A
    preview[(a == 0) & (b != 0)] = [255, 190, 45]  # only B
    preview[(a != 0) & (b != 0) & (a != b)] = [255, 65, 65]  # conflict
    preview[both_same] = [65, 175, 110]  # same labeled class
    image_buf = io.BytesIO()
    Image.fromarray(preview).save(image_buf, format="PNG")
    summary = {"status": "NEEDS_HUMAN_ADJUDICATION", "ground_truth_verified": False,
               "same_rgb_and_depth_sha256": True,
               "source_rgb_sha256": qa["sources"]["rgb"]["sha256"],
               "source_depth_sha256": qa["sources"]["depth"]["sha256"],
               "image_size": {"width": a.shape[1], "height": a.shape[0]},
               "annotated_union_pixels": union_count, "same_class_labeled_pixels": agreement,
               "disagreement_pixels": int(mismatch.sum()),
               "labeled_agreement_iou": round(agreement / union_count, 6) if union_count else None,
               "class_iou": metrics,
               "warning": "Agreement is not accuracy. The system cannot verify that annotators are independent or labels are correct.",
               "legend": {"green": "both same class", "pink": "A only", "orange": "B only", "red": "conflicting classes", "black": "both unknown"}}
    return summary, image_buf.getvalue()
