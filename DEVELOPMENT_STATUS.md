# Eeksha development status

Baseline: uploaded `eeksha-mvp6.zip`, inspected 2026-11-08.

## Verified locally

- 12 automated tests passed via `python -m unittest -v`.
- Synthetic aligned RGB-D to semantic point-cloud export (`.ply`, `.npz`).
- Local Flask browser import, visualization and ZIP report download.
- WE3DS 16-bit refined-depth import, 19-class semantic mask handling and 2D QA previews.
- Calibration-source-gated WE3DS geometric export (code path tested on synthetic tiny input).

## Not established

- No independently verified camera intrinsics for the imported WE3DS sample.
- No independently measured geometric accuracy benchmark.
- No evidence of production deployment, customer use, or proprietary field collection.
- The WE3DS refined depth is interpolated; filled coverage is not sensor-valid coverage.

## Next milestone

Import one RGB-D agricultural scene with authentic aligned intrinsics, export metric 3D,
and validate distances against independent physical reference measurements. Record
camera model, calibration provenance, image alignment, depth scale, error statistics,
and dataset attribution. Only then call that scene geometrically validated.
