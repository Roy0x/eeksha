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

### Real broccoli field RGB-D validation (Mendeley dataset v3)

The independently published [baby-broccoli RGB-D dataset](https://doi.org/10.17632/px5p6zdk6k.3)
is licensed CC BY 4.0. Download `camera_intrinsics.json` and matching
`day_rgb_XXXX.png` / `day_depth_XXXX.png` pairs. Keep the inputs outside the
repository. Then run:

```bash
python real_field_demo.py --input /path/to/input --output /path/to/results --limit 3
```

The adapter takes the **aligned-to-RGB** intrinsics and millimetre axial-Z
convention explicitly documented in the supplied metadata. It excludes zero
and out-of-range depth and writes point clouds, per-pair QA, and
`field_summary.json`. **All points have class `unknown` (0)** because the
provided RGB-D frames have no pixel-level semantic masks. This is not crop
segmentation or an independent metric-accuracy benchmark. The original
authors retain credit for capturing and curating the field data.

### Manual polygon annotation → labeled 3D

Start the local Flask app (`python webapp.py`) and open
`http://127.0.0.1:8012/annotator`. Load a matching RGB PNG, 16-bit depth
PNG, and the published `camera_intrinsics.json`. Draw polygons around broccoli
heads, leaves, soil, other crop, or weeds; finish each polygon before exporting.
The ZIP includes `annotations.json`, `labels.png`, calibrated PLY/NPZ, the
original calibration, and quality reports. Pixels outside polygons remain
`unknown`. The manual annotations are explicitly **unreviewed**, neither AI
predictions nor independent ground truth. Class IDs now include broccoli head
(4) and broccoli leaf (5), in addition to unknown (0), soil (1), crop (2),
weed (3).

For curved boundaries, **press and drag** to trace with a mouse, touch screen,
or pen. Single clicks still add precise corner vertices. The RGB photo remains
in a separate static layer; pointer movement paints only new overlay segments
and the exported stroke simplifies redundant vertices before
export. Release the pointer and select **Finish polygon**. Use Undo or Remove
to correct a trace; do not draw broad polygons around a broccoli head and its
surrounding leaves under the same class.

### V0.4 / Annotation agreement and disagreement review

Open `http://127.0.0.1:8012/review` from the same local Flask app.
Upload two Eeksha annotation-export ZIPs for the same scene, ideally drawn
independently. The comparison validates recorded polygon-to-mask consistency,
checks RGB/depth source hashes and calibration equality, calculates per-class
intersection-over-union (IoU), and displays a disagreement map. The review
state always remains `NEEDS_HUMAN_ADJUDICATION`: agreement is **not** accuracy
or ground truth. Annotator identity and independence are not authenticated.
To make a genuine quality claim, recruit a second annotator and have a reviewer
resolve the colored disagreement regions before issuing an approved dataset.

### V0.6 / Human brush correction and auditable 3D re-export

Open `http://127.0.0.1:8012/correct`. Select the RGB PNG and click
**Start blank annotation**. Every pixel starts as UNKNOWN. The browser editor
no longer requires or imports any older annotation ZIP. Paint new semantic
classes, use `Eraser / unknown`, and undo/redo strokes. For 3D export, provide
matching RGB/depth PNGs, original `camera_intrinsics.json`, and reviewer ID.
The package contains `labels.png`, corresponding 3D PLY/NPZ and an auditable
`correction_audit.json`. New brush labeling is marked `UNREVIEWED`, not ground
truth. The original ZIP-based correction functions remain available to older
clients, but are not exposed on the new annotation page.
The brush and zoom experience should be tested on the target laptop and in
browser before claiming production-ready annotation ergonomics.
The correction page previews an RGB PNG immediately after selection. Drawing
remains disabled until a fresh blank label mask is initialized. A failed image
decode is displayed beside the preview.

### V0.7 / Correction coverage evidence

Corrected exports include `correction_quality.json`, with original/corrected
pixel counts, valid-depth point counts for every semantic class, and the number
of changed image pixels that have no usable depth. The correction page shows
the broccoli-head comparison and an embedded corrected 3D viewer after export.
These metrics establish completeness/coverage only, not label correctness or
geometric accuracy. The original ZIP and correction strokes remain auditable.

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
