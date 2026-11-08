"""Small, auditable RGB-D to semantic point cloud pipeline."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image

CLASSES = {0: "unknown", 1: "soil", 2: "crop", 3: "weed"}


def process(rgb_path: Path, depth_path: Path, labels_path: Path, calibration_path: Path,
            output: Path, max_depth_m: float = 5.0) -> dict:
    rgb = np.asarray(Image.open(rgb_path).convert("RGB"))
    depth = np.asarray(Image.open(depth_path))
    labels = np.asarray(Image.open(labels_path))
    if depth.ndim != 2 or labels.ndim != 2 or rgb.shape[:2] != depth.shape or depth.shape != labels.shape:
        raise ValueError("RGB, depth, and labels must have identical image dimensions; depth/labels must be single-channel")
    if not np.issubdtype(depth.dtype, np.integer) and not np.issubdtype(depth.dtype, np.floating):
        raise ValueError("Depth must be numeric")
    if not np.issubdtype(labels.dtype, np.integer) or not np.isin(labels, list(CLASSES)).all():
        raise ValueError("Labels must be integer class IDs 0, 1, 2, or 3")
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    for key in ("fx", "fy", "cx", "cy", "depth_scale"):
        if key not in calibration or isinstance(calibration[key], bool) or not isinstance(calibration[key], (int, float)) or not np.isfinite(calibration[key]):
            raise ValueError(f"Missing or non-finite calibration value: {key}")
    fx, fy = float(calibration["fx"]), float(calibration["fy"])
    scale = float(calibration["depth_scale"])
    if fx <= 0 or fy <= 0 or scale <= 0 or max_depth_m <= 0:
        raise ValueError("Focal lengths, depth scale and max depth must be positive")
    if calibration.get("width", rgb.shape[1]) != rgb.shape[1] or calibration.get("height", rgb.shape[0]) != rgb.shape[0]:
        raise ValueError("Calibration dimensions do not match images")
    depth_type = calibration.get("depth_type")
    if depth_type not in ("axial_z", "ray_distance"):
        raise ValueError("Calibration must explicitly specify depth_type as axial_z or ray_distance")
    measured = depth.astype(np.float64) * scale
    valid = np.isfinite(measured) & (measured > 0) & (measured <= max_depth_m)
    if not valid.any():
        raise ValueError("No valid depth samples")
    v, u = np.nonzero(valid)
    rx = (u - calibration["cx"]) / fx
    ry = (v - calibration["cy"]) / fy
    zz = measured[valid]
    if depth_type == "ray_distance":
        zz = zz / np.sqrt(1 + rx * rx + ry * ry)
    xyz = np.column_stack((rx * zz, ry * zz, zz))
    colors = rgb[valid]
    classes = labels[valid]
    output.mkdir(parents=True, exist_ok=True)
    ply_path = output / "semantic_cloud.ply"
    with ply_path.open("w", encoding="ascii") as stream:
        stream.write("ply\nformat ascii 1.0\n")
        stream.write(f"element vertex {len(xyz)}\n")
        stream.write("property float x\nproperty float y\nproperty float z\n")
        stream.write("property uchar red\nproperty uchar green\nproperty uchar blue\nproperty uchar class_id\nend_header\n")
        for point, color, cls in zip(xyz, colors, classes):
            stream.write(f"{point[0]:.8f} {point[1]:.8f} {point[2]:.8f} {color[0]} {color[1]} {color[2]} {int(cls)}\n")
    np.savez_compressed(output / "semantic_cloud.npz", xyz=xyz.astype(np.float32), rgb=colors, labels=classes)
    report = {
        "status": "PASS", "points": len(xyz), "pixels": int(depth.size),
        "depth_coverage": round(float(valid.mean()), 6),
        "class_counts": {name: int((classes == code).sum()) for code, name in CLASSES.items()},
        "bounds_m": {axis: [float(xyz[:, i].min()), float(xyz[:, i].max())] for i, axis in enumerate("xyz")},
        "calibration": calibration, "depth_type": depth_type, "max_depth_m": max_depth_m,
        "sources": {name: {"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                    for name, path in [("rgb", rgb_path), ("depth", depth_path), ("labels", labels_path), ("calibration", calibration_path)]},
        "limitations": ["No independent ground-truth geometry validation", "Labels imported, not predicted",
                        "Assumes aligned RGB/depth/labels and distortion-corrected pixels"]
    }
    (output / "qa_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def make_demo(folder: Path) -> None:
    """Synthetic geometry for testing only; never represent as field-collected data."""
    folder.mkdir(parents=True, exist_ok=True)
    h, w = 90, 120
    yy, xx = np.indices((h, w))
    crop = ((xx - 38) ** 2 / 20 ** 2 + (yy - 41) ** 2 / 28 ** 2) < 1
    weed = ((xx - 83) ** 2 / 12 ** 2 + (yy - 54) ** 2 / 16 ** 2) < 1
    labels = np.ones((h, w), dtype=np.uint8)
    labels[crop] = 2
    labels[weed] = 3
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[:] = [117, 90, 60]
    rgb[crop] = [55, 147, 65]
    rgb[weed] = [115, 185, 65]
    depth = np.full((h, w), 1250, dtype=np.uint16)
    depth[crop] = 950
    depth[weed] = 1050
    depth[:3] = 0
    Image.fromarray(rgb).save(folder / "rgb.png")
    Image.fromarray(depth).save(folder / "depth.png")
    Image.fromarray(labels).save(folder / "labels.png")
    (folder / "calibration.json").write_text(json.dumps({"fx": 110, "fy": 110, "cx": 59.5,
                                                          "cy": 44.5, "depth_scale": 0.001,
                                                          "width": w, "height": h, "depth_type": "axial_z"}, indent=2))
