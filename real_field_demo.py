"""Reproducible Eeksha field RGB-D import; no semantic labels are inferred."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from eeksha import process


def convert_intrinsics(source: Path, target: Path) -> dict:
    """Use published RGB intrinsics because depth is aligned to RGB."""
    raw = json.loads(source.read_text(encoding="utf-8"))
    notes = raw.get("usage_notes", {})
    if "aligned to the RGB" not in notes.get("depth_alignment", ""):
        raise ValueError("Cannot verify depth-to-RGB alignment from metadata")
    if "Z is depth in mm" not in notes.get("coordinate_formula", ""):
        raise ValueError("Cannot verify millimetre axial-Z depth convention")
    resolution = raw["resolution"]
    intrinsics = raw["rgb_intrinsics"]
    if any(float(v) != 0 for v in intrinsics.get("distortion_coefficients", [])):
        raise ValueError("Nonzero distortion coefficients require rectification")
    config = {key: float(intrinsics[key]) for key in ("fx", "fy", "cx", "cy")}
    config.update(width=int(resolution["width"]), height=int(resolution["height"]),
                  depth_scale=0.001, depth_type="axial_z",
                  source="Mendeley Data 10.17632/px5p6zdk6k.3, camera_intrinsics.json")
    target.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def run(source: Path, destination: Path, limit: int = 3, max_depth_m: float = 2.0) -> dict:
    if limit < 1:
        raise ValueError("limit must be positive")
    destination.mkdir(parents=True, exist_ok=True)
    calibration_path = destination / "derived_calibration.json"
    convert_intrinsics(source / "camera_intrinsics.json", calibration_path)
    pairs = []
    missing = []
    for rgb_path in sorted(source.glob("day_rgb_*.png")):
        number = rgb_path.stem.removeprefix("day_rgb_")
        depth_path = source / f"day_depth_{number}.png"
        if not depth_path.is_file():
            missing.append(number)
            continue
        pairs.append((number, rgb_path, depth_path))
    if not pairs:
        raise ValueError("No matching daytime RGB/depth pairs")
    results = []
    for number, rgb_path, depth_path in pairs[:limit]:
        folder = destination / number
        folder.mkdir(exist_ok=True)
        depth = np.asarray(Image.open(depth_path))
        if depth.dtype != np.uint16:
            raise ValueError(f"{depth_path.name} must be uint16")
        # No ground-truth semantic segmentation is provided. Class 0 means UNKNOWN.
        label_path = folder / "unknown_labels.png"
        Image.fromarray(np.zeros(depth.shape, dtype=np.uint8)).save(label_path)
        qa = process(rgb_path, depth_path, label_path, calibration_path, folder,
                     max_depth_m=max_depth_m)
        qa["semantic_status"] = "UNLABELED_ALL_UNKNOWN"
        qa["raw_nonzero_depth_fraction"] = round(float(np.mean(depth > 0)), 6)
        qa["source_dataset"] = "10.17632/px5p6zdk6k.3"
        (folder / "qa_report.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
        results.append({"pair": number, "points": qa["points"],
                        "valid_depth_coverage": qa["depth_coverage"],
                        "raw_nonzero_depth_fraction": qa["raw_nonzero_depth_fraction"]})
    report = {"dataset": "10.17632/px5p6zdk6k.3", "processed_pairs": results,
              "missing_depth_for_rgb": missing,
              "semantic_status": "UNLABELED_ALL_UNKNOWN",
              "independent_geometry_accuracy": "NOT_MEASURED",
              "license": "CC BY 4.0; attribution required"}
    (destination / "field_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--max-depth-m", type=float, default=2.0)
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output, args.limit, args.max_depth_m), indent=2))
