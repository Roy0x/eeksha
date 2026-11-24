"""Compare Eeksha QA exports from the exact same source scene.

Counts and coverage are observational evidence, not ground-truth accuracy.
"""
from __future__ import annotations

import io
import json
import math
import zipfile

MAX_ARCHIVE_BYTES = 30 * 1024 * 1024
MAX_REPORT_BYTES = 1024 * 1024
CLASSES = ("unknown", "soil", "crop", "weed", "broccoli_head", "broccoli_leaf")


def load_qa(archive_bytes: bytes) -> dict:
    if not archive_bytes or len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise ValueError("QA ZIP is empty or exceeds 30 MB")
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)) or names.count("qa_report.json") != 1:
                raise ValueError("ZIP must contain exactly one qa_report.json")
            if len(members) > 32 or sum(member.file_size for member in members) > 60 * 1024 * 1024:
                raise ValueError("QA ZIP exceeds extraction safety limits")
            report_member = archive.getinfo("qa_report.json")
            if report_member.file_size > MAX_REPORT_BYTES:
                raise ValueError("QA report is too large")
            report = json.loads(archive.read("qa_report.json"))
    except (zipfile.BadZipFile, KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid Eeksha QA ZIP") from error
    if not isinstance(report, dict):
        raise ValueError("QA report must be a JSON object")
    for name in ("rgb", "depth", "labels"):
        source = report.get("sources", {}).get(name)
        if not isinstance(source, dict) or not isinstance(source.get("sha256"), str) or len(source["sha256"]) != 64:
            raise ValueError(f"Missing {name} source SHA-256")
    if not isinstance(report.get("calibration"), dict):
        raise ValueError("Missing calibration")
    counts = report.get("class_counts")
    if not isinstance(counts, dict) or any(type(counts.get(name)) is not int or counts[name] < 0 for name in CLASSES):
        raise ValueError("Invalid semantic class counts")
    points = report.get("points")
    coverage = report.get("depth_coverage")
    if type(points) is not int or points < 0 or sum(counts[name] for name in CLASSES) != points:
        raise ValueError("Class counts disagree with point total")
    if type(coverage) not in (float, int) or not math.isfinite(coverage) or not 0 <= coverage <= 1:
        raise ValueError("Invalid depth coverage")
    return report


def compare_qa(before_zip: bytes, after_zip: bytes) -> dict:
    before, after = load_qa(before_zip), load_qa(after_zip)
    for name in ("rgb", "depth"):
        if before["sources"][name]["sha256"] != after["sources"][name]["sha256"]:
            raise ValueError(f"Cannot compare different source {name.upper()} images")
    if before["calibration"] != after["calibration"]:
        raise ValueError("Cannot compare different camera calibrations")
    if before.get("max_depth_m") != after.get("max_depth_m"):
        raise ValueError("Cannot compare different depth limits")
    b, a = before["class_counts"], after["class_counts"]
    bp, ap = before["points"], after["points"]
    labeled_before = bp - b["unknown"]
    labeled_after = ap - a["unknown"]
    return {
        "status": "COMPARABLE_SOURCE_MATCHED_REPORTS",
        "same_source_rgb_depth": True,
        "source_labels_changed": before["sources"]["labels"]["sha256"] != after["sources"]["labels"]["sha256"],
        "points_before": bp, "points_after": ap, "point_delta": ap - bp,
        "depth_coverage_before": before["depth_coverage"],
        "depth_coverage_after": after["depth_coverage"],
        "labeled_valid_points_before": labeled_before,
        "labeled_valid_points_after": labeled_after,
        "labeled_valid_fraction_before": round(labeled_before / bp, 6) if bp else 0.0,
        "labeled_valid_fraction_after": round(labeled_after / ap, 6) if ap else 0.0,
        "class_deltas": {name: a[name] - b[name] for name in CLASSES},
        "review_status_before": before.get("annotation_review", "NOT_RECORDED"),
        "review_status_after": after.get("annotation_review", "NOT_RECORDED"),
        "ground_truth_verified": False,
        "warning": "Comparable changes in coverage and labels do not establish semantic correctness or metric geometric accuracy.",
    }
