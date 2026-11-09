# Eeksha MVP release status — 2026-11-09

## Implemented and verified

- Local-only Flask interface for calibrated aligned RGB-D ingestion and semantic 3D exploration.
- Synthetic demo; manual polygon labeling; brush labeling and erasing; undo/redo and zoom.
- Resume previously exported brush and polygon dataset ZIPs after validating original label SHA-256 and RGB provenance.
- Corrected 3D PLY/NPZ export with QA, brush-stroke provenance, and unchanged nested original ZIP.
- Per-region broccoli-head pixel and depth-coverage audit, with low-depth and border flags.
- 33 automated tests passed with `python -m unittest discover -q`.
- Real sample smoke test passed with the user-supplied `eeksha-dataset (3).zip`, `day_rgb_0001.png`, `day_depth_0001.png`, and `camera_intrinsics.json`:
  - One known false-positive right-edge region (868 pixels) changed to UNKNOWN.
  - Four significant broccoli-head mask regions remain.
  - 8,759 broccoli-head pixels have valid depth; 141,200 total valid-depth points.
  - Output archive CRC verified, original ZIP preserved, not independently verified ground truth.
- Confirmed through a connected Chrome browser: the live Windows editor restored previous masks and permitted eraser correction.

## Explicit limitations

- Human labeling and the one-region removal are **not independently verified semantic ground truth**.
- Bottom broccoli head has poor valid-depth coverage (~7.7% in the original annotation). Label painting cannot manufacture missing physical depth.
- No hardware benchmark, robotics deployment, measured geometric error, or independent multi-annotator adjudication.
- Eeksha's app is local development software, not a secure multi-user SaaS service.
- The connected Chrome automation could not select local files due to extension file-access restrictions; the human completed file selection in the live UI.

## MVP completion boundary

The **local demonstration MVP is complete** for the stated input → annotation → calibrated point cloud → QA → ZIP workflow. Do not claim a production-ready robotics dataset platform or calibrated field accuracy without physical measurements and independent annotation review.
