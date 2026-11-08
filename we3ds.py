"""WE3DS real-data ingestion without claiming unprovided camera calibration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

CLASS_NAMES = (
    "void", "soil", "broad bean", "corn spurry", "red-root amaranth",
    "common buckwheat", "pea", "red fingergrass", "common wild oat",
    "cornflower", "corn cockle", "corn", "milk thistle", "rye brome",
    "soybean", "sunflower", "narrow-leaved plantain",
    "small-flower geranium", "sugar beet",
)


def export_calibrated_we3ds(rgb_path: Path, depth_path: Path, labels_path: Path,
                            calibration_path: Path, output: Path, point_limit: int = 50000) -> dict:
    """Reconstruct only with explicitly sourced intrinsics for the cropped WE3DS image."""
    if not isinstance(point_limit, int) or point_limit < 1:
        raise ValueError("point_limit must be a positive integer")
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    if calibration.get("source_type") != "measured_rectified_cropped_intrinsics":
        raise ValueError("Calibration source_type must be measured_rectified_cropped_intrinsics")
    if not isinstance(calibration.get("source_reference"), str) or not calibration["source_reference"].strip():
        raise ValueError("Calibration must include a source_reference for audit")
    if calibration.get("depth_type") != "ray_distance":
        raise ValueError("WE3DS depth_type must be ray_distance")
    if calibration.get("depth_scale") != 0.0001:
        raise ValueError("WE3DS depth_scale must equal 0.0001 metres per unit")
    with Image.open(rgb_path) as image:
        rgb = np.asarray(image.convert("RGB"))
    with Image.open(depth_path) as image:
        if image.mode not in ("I;16", "I;16L", "I;16B"):
            raise ValueError("Expected original 16-bit WE3DS depth PNG")
        depth = np.asarray(image)
    with Image.open(labels_path) as image:
        labels = np.asarray(image)
    if depth.ndim != 2 or labels.ndim != 2 or depth.shape != labels.shape or rgb.shape[:2] != depth.shape:
        raise ValueError("Inputs must be aligned")
    if np.any(labels >= len(CLASS_NAMES)) or not np.issubdtype(labels.dtype, np.integer):
        raise ValueError("Unsupported class IDs")
    height, width = depth.shape
    if calibration.get("width") != width or calibration.get("height") != height:
        raise ValueError("Calibration must match the cropped image width and height")
    for key in ("fx", "fy", "cx", "cy"):
        number = calibration.get(key)
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not np.isfinite(number):
            raise ValueError(f"Missing or invalid calibrated {key}")
    fx, fy, cx, cy = (float(calibration[k]) for k in ("fx", "fy", "cx", "cy"))
    if fx <= 0 or fy <= 0 or not (0 <= cx < width and 0 <= cy < height):
        raise ValueError("Focal lengths must be positive and optical centre within image")
    coords = np.flatnonzero(depth > 0)
    if not len(coords):
        raise ValueError("No valid depth")
    stride = max(1, int(np.ceil(len(coords) / point_limit)))
    coords = coords[::stride]
    v, u = np.divmod(coords, width)
    rx = (u - cx) / fx
    ry = (v - cy) / fy
    ray_distance = depth.flat[coords].astype(np.float64) * 0.0001
    z = ray_distance / np.sqrt(1 + rx ** 2 + ry ** 2)
    xyz = np.column_stack((rx * z, ry * z, z)).astype(np.float32)
    colors = rgb.reshape(-1, 3)[coords]
    classes = labels.flat[coords].astype(np.uint8)
    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output / "semantic_cloud.npz", xyz=xyz, rgb=colors, labels=classes)
    with (output / "semantic_cloud.ply").open("w", encoding="ascii") as stream:
        stream.write("ply\nformat ascii 1.0\n")
        stream.write(f"element vertex {len(coords)}\n")
        stream.write("property float x\nproperty float y\nproperty float z\n")
        stream.write("property uchar red\nproperty uchar green\nproperty uchar blue\nproperty uchar class_id\nend_header\n")
        for xyz_row, color, class_id in zip(xyz, colors, classes):
            stream.write(f"{xyz_row[0]:.7f} {xyz_row[1]:.7f} {xyz_row[2]:.7f} "
                         f"{color[0]} {color[1]} {color[2]} {int(class_id)}\n")
    report = {
        "dataset": "WE3DS", "status": "CALIBRATED_RECONSTRUCTION_UNVERIFIED_GEOMETRY",
        "points": int(len(coords)), "sampling_stride": stride,
        "calibration_source_reference": calibration["source_reference"],
        "calibration_sha256": hashlib.sha256(calibration_path.read_bytes()).hexdigest(),
        "limitations": ["Calibration provenance user-supplied; not independently verified by Eeksha",
                        "No independent geometry accuracy benchmark", "Refined depth includes interpolated measurements",
                        "Source data was collected by WE3DS, not Eeksha"],
    }
    (output / "geometry_qa_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def inspect_we3ds(rgb_path: Path, depth_path: Path, labels_path: Path, output: Path) -> dict:
    """Validate aligned WE3DS imagery, save previews and a non-3D QA report."""
    with Image.open(rgb_path) as im:
        if im.mode not in ("RGB", "RGBA"):
            raise ValueError("WE3DS RGB file must contain an RGB or RGBA image")
        rgb = np.asarray(im.convert("RGB"))
    with Image.open(depth_path) as im:
        if im.mode not in ("I;16", "I;16L", "I;16B"):
            raise ValueError("WE3DS depth must be a 16-bit grayscale PNG; do not convert to 8-bit")
        depth = np.asarray(im)
    with Image.open(labels_path) as im:
        if im.mode != "L":
            raise ValueError("WE3DS ground truth must be an 8-bit class-index mask")
        labels = np.asarray(im)
    if rgb.shape[:2] != depth.shape or labels.shape != depth.shape:
        raise ValueError("RGB, depth, and labels must have identical dimensions")
    if not np.isin(labels, range(len(CLASS_NAMES))).all():
        raise ValueError("Mask contains unsupported WE3DS class IDs")
    if not np.any(depth):
        raise ValueError("Depth has no nonzero measurements")

    # The original WE3DS distance-map values use units of 0.1 mm.
    depth_m = depth.astype(np.float32) / 10000.0
    valid = depth > 0
    counts = {CLASS_NAMES[int(i)]: int(n) for i, n in zip(*np.unique(labels, return_counts=True))}
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(output / "rgb_preview.png")

    low, high = np.percentile(depth_m[valid], [2, 98])
    normalized = np.zeros(depth.shape, dtype=np.uint8)
    if high > low:
        normalized[valid] = np.clip((depth_m[valid] - low) / (high - low) * 255, 0, 255).astype(np.uint8)
    # Depth preview is explicitly a contrast-stretched visual, not numeric depth.
    Image.fromarray(normalized).save(output / "depth_preview.png")
    palette = np.zeros((len(CLASS_NAMES), 3), dtype=np.uint8)
    palette[1] = (123, 91, 68)
    for i in range(2, len(CLASS_NAMES)):
        palette[i] = ((i * 73) % 210 + 30, (i * 107) % 190 + 40, (i * 47) % 210 + 30)
    overlay = rgb.astype(np.float32)
    known = labels != 0
    overlay[known] = 0.55 * overlay[known] + 0.45 * palette[labels[known]]
    Image.fromarray(overlay.astype(np.uint8)).save(output / "semantic_overlay.png")

    report = {
        "dataset": "WE3DS", "status": "VALID_2D_INPUT", "width": int(depth.shape[1]),
        "height": int(depth.shape[0]), "depth_unit_m": 0.0001,
        "depth_type": "ray_distance", "depth_min_m": float(depth_m[valid].min()),
        "depth_max_m": float(depth_m[valid].max()),
        "depth_coverage": float(valid.mean()), "class_counts": counts,
        "calibration_status": "MISSING_INTRINSICS",
        "three_d_export": "BLOCKED_UNTIL_INTRINSICS_VERIFIED",
        "limitations": [
            "No verified calibrated fx/fy/cx/cy for this image; geometric point cloud not exported",
            "Refined depth contains interpolated values; depth coverage is not sensor-validity coverage",
            "Class masks are imported human annotations, not model predictions",
            "Data originates from WE3DS, not Eeksha field collection",
        ],
        "sources": {
            name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "filename": path.name}
            for name, path in (("rgb", rgb_path), ("depth_refined", depth_path), ("ground_truth", labels_path))
        },
    }
    (output / "qa_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
