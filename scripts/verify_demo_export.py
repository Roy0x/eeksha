"""Verify structural integrity of a synthetic Eeksha CLI export.

This is a smoke test, not proof of agricultural labeling or 3D accuracy.
"""
import json
import sys
from pathlib import Path

import numpy as np


def verify(directory: Path) -> None:
    expected = ("semantic_cloud.ply", "semantic_cloud.npz", "qa_report.json", "viewer.html")
    missing = [name for name in expected if not (directory / name).is_file()]
    if missing:
        raise RuntimeError(f"Missing export files: {', '.join(missing)}")

    qa = json.loads((directory / "qa_report.json").read_text(encoding="utf-8"))
    if qa.get("synthetic_demo") is not True:
        raise RuntimeError("QA report must explicitly identify synthetic data")
    if qa.get("status") != "PASS":
        raise RuntimeError(f"Export did not pass structural QA: {qa.get('status')}")
    if not isinstance(qa.get("points"), int) or qa["points"] <= 0:
        raise RuntimeError("QA report has no positive point count")

    with np.load(directory / "semantic_cloud.npz", allow_pickle=False) as cloud:
        if not cloud.files:
            raise RuntimeError("NPZ export is empty")
        rows = {key: int(cloud[key].shape[0]) for key in cloud.files if cloud[key].ndim}
        if not rows or qa["points"] not in rows.values():
            raise RuntimeError("NPZ arrays do not match QA point count")

    ply = (directory / "semantic_cloud.ply").read_bytes()
    if not ply.startswith(b"ply\n") or b"end_header\n" not in ply[:8192]:
        raise RuntimeError("PLY header missing")
    viewer = (directory / "viewer.html").read_text(encoding="utf-8")
    if "<html" not in viewer.lower():
        raise RuntimeError("HTML viewer missing markup")
    print(f"PASS: synthetic export integrity ({qa['points']} points)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/verify_demo_export.py OUTPUT_DIR")
    verify(Path(sys.argv[1]))
