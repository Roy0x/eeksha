# Eeksha MVP

An auditable **RGB-D → calibrated 3D point cloud → semantic labels → quality report → export** pipeline for agricultural robotics research.

## Quick start

From this folder, with Python 3.10+:

```bash
python -m pip install -r requirements.txt
python run.py --demo
python -m unittest -v
```

## Browser application (new)

Run `python webapp.py` and open **http://127.0.0.1:8012** in Chrome.

Choose all four aligned input files and press **Process real input**, or select **Load synthetic example** to explore without hardware. The page shows a rotatable 3D semantic scene and lets you download a ZIP containing the PLY, NPZ and QA report. It runs only on localhost and is not intended for public hosting. Maximum upload request: 30 MB.

`--demo` generates **synthetic test pixels**, not real agricultural observations. For real data, supply four aligned input files in `sample/` (or set `--input DIR`):

- `rgb.png`: 8-bit RGB image
- `depth.png`: single-channel depth in units determined by the calibration `depth_scale`
- `labels.png`: matching single-channel class IDs: 0 unknown, 1 soil, 2 crop, 3 weed
- `calibration.json`: `fx`, `fy`, `cx`, `cy`, `depth_scale` (metres per depth unit), `depth_type` (`axial_z` or `ray_distance`), and optionally `width`, `height`

The input must already be registered/aligned and distortion-corrected. Incorrect camera intrinsics produce incorrect geometry; this program cannot infer calibration from an image.
`axial_z` means the encoded depth is along the optical axis; `ray_distance` means Euclidean distance from the camera center to the measured point. Eeksha requires the distinction to be explicit and rejects missing `depth_type`. Do not guess a depth scale or type for a research dataset.

Outputs in `output/`:

- `semantic_cloud.ply`: ASCII PLY with xyz, RGB, and `class_id` vertex attributes
- `semantic_cloud.npz`: compressed arrays for training pipelines
- `qa_report.json`: coverage, counts, metric bounds, provenance SHA-256s and known limitations
- `viewer.html`: self-contained interactive projected 3D viewer; open directly in Chrome (no server or internet required)

The viewer includes rotate, zoom, class filters and point-size controls. It displays a downsampled preview when a cloud exceeds 12,000 points; exported datasets retain all valid points.

## Scope and truthfulness

The MVP processes **existing** semantic masks; it does not train a model, predict weeds, calibrate sensors, independently prove 3D accuracy, or operate robots. QA checks structural validity, not crop-safe actuation accuracy. Export is an interoperability starting point, not a universal robotics standard.

Suggested next step: run a real licensed agricultural RGB-D scene with its supplied camera calibration and labels, then record geometric accuracy against independent ground truth.
# WE3DS real-data inspection (new)

Run `py -3.13 webapp.py`, open `http://127.0.0.1:8012`, then use **WE3DS / Real dataset inspector**.
Upload matching files from the same WE3DS image ID: `data` (RGB),
`fields/depth_refined` (16-bit distance map), and `fields/ground_truth` (class-index mask).
The importer preserves all 19 WE3DS class IDs, interprets values in 0.1 mm units,
produces RGB/depth/semantic previews and an evidence-based QA report.
It deliberately **does not generate a 3D point cloud** without verified camera intrinsics.
WE3DS is an external dataset by Kitzler et al. (2023), not Eeksha-collected data.

## Conditional calibrated 3D export

The WE3DS authors report stereo calibration **per measurement date**, followed by
rectification and cropping to 1600x1144. The public dataset card describes the
camera setup, but does not provide the exact effective rectified/cropped intrinsics
in its per-image fields. A nominal 12mm lens specification is **not a substitute**.

If you obtain authenticated, image-aligned parameters from the original dataset
authors or instrument records, make a calibration JSON like this (values for the
four intrinsics below are placeholders and must be replaced, not used as-is):

```json
{
  "source_type": "measured_rectified_cropped_intrinsics",
  "source_reference": "REPLACE_WITH_AUDITABLE_RECORD_REFERENCE",
  "width": 1600,
  "height": 1144,
  "fx": 0,
  "fy": 0,
  "cx": 0,
  "cy": 0,
  "depth_type": "ray_distance",
  "depth_scale": 0.0001
}
```

Export only after correcting every placeholder and verifying the parameters
apply to the exact image, measurement date, rectification, and crop:

```powershell
py -3.13 calibrated_export.py --rgb rgb.png --depth depth_refined.png --labels ground_truth.png --calibration calibration.json
```

This exported result remains *unverified geometric reconstruction* until
checked against independent reference geometry. Attribution: Kitzler et al.,
*WE3DS: An RGB-D Image Dataset for Semantic Segmentation in Agriculture*,
Sensors 2023, DOI: 10.3390/s23052713.
