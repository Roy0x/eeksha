# Eeksha AI: First-user walkthrough

**Release:** Public research preview, November 2026  
**Expected time:** Self-paced; no cloud account or paid API key required  
**Who this is for:** Agricultural robotics engineers, perception researchers, and dataset annotators

## Step 1 — Run the local application

From a clean checkout of the launch candidate:

```powershell
git clone https://github.com/Roy0x/eeksha.git
cd eeksha
git switch feat/eeksha-ci-repro-20261113
py -3.13 -m pip install -r requirements.txt
py -3.13 -m unittest -v
py -3.13 webapp.py
```

Visit http://127.0.0.1:8022/workspace . The server intentionally listens on loopback only.

## Step 2 — Verify the synthetic path

Choose **Synthetic demo**, inspect the 3D scene, class counts, depth coverage and export ZIP. This demonstrates software behavior, **not** field data, model predictions, or measured geometric accuracy.

## Step 3 — Real images and source licensing

For real-field input, use images you own or are permitted to process, with verified RGB registration and camera calibration. Eeksha's supported reference is the independently published baby-broccoli RGB-D dataset:

- DOI: https://doi.org/10.17632/px5p6zdk6k.3
- Dataset authors own the original data. Preserve attribution and CC BY 4.0 license notices.
- Download `camera_intrinsics.json` and a matching `day_rgb_XXXX.png` / `day_depth_XXXX.png` pair **from the source**; do not fabricate calibration.
- These frames do not include pixel-level semantic labels. Existing labels must not be represented as ML outputs or independently checked ground truth.

To perform a real-data 3D import without inventing labels:

```powershell
py -3.13 real_field_demo.py --input C:\path\to\broccoli-input --output C:\path\to\eeksha-results --limit 1
```

Check the output summary and ensure every imported semantic label remains `unknown` until a human supplies annotations.

## Step 4 — Label and inspect

1. Open `http://127.0.0.1:8022/annotator` for polygons or `/correct` for brush correction.
2. Provide the **same** RGB, depth and source camera metadata to the annotation workflow.
3. Use the editor to draw a small test class region and export the dataset ZIP.
4. Open `/workspace`; select RGB, depth, exported `labels.png` and the Eeksha-compatible `calibration.json` from the export.
5. If using original published `camera_intrinsics.json`, select it in the workspace and click **Convert source camera_intrinsics.json**. This applies only to the supported published metadata format, uses its documented alignment and units, and does not overwrite the source. Skip conversion if you already have Eeksha-compatible `calibration.json`.
6. Choose **Check input readiness**. The preflight checks image formats, dimensions, class IDs and required numeric calibration fields.
7. Choose **Process real scene**. Review the source provenance warning and structural QA.
8. Download the ZIP. Check that the PLY, NPZ and JSON report agree with the source and that class counts are plausible.

Preflight is only **structural**. It cannot prove that the input camera parameters are true, pixels are registered, labels are correct, or the resulting geometry is safe for actuation.

## Step 5 — Independent review

Use `/review` to compare two independently produced annotation exports for the same source scene. Reconcile disagreements with a person, record decisions, and never equate agreement with accuracy.

## Expected feedback from first external testers

Record the tester's role and whether they have rights to the sample imagery. Ask:

- Could you install and run the workspace without developer assistance?
- At which step did the instructions become unclear?
- Were incorrect source dimensions and missing depth conventions reported clearly?
- Can you find the origin/provenance and limitations of the exported labels?
- Is the output compatible with your downstream robotics research workflow?
- What costly manual step could this replace for your team?

Collect reported time-to-first-success, concrete reproducible failures, and whether they would repeat the workflow with their own dataset. Do **not** claim interviews or usage that haven't occurred.

## Known limitations and release gate

- No automatic crop or weed segmentation, camera calibration, independently measured geometry, or robot control.
- Existing hosted web app is **not** public: only the static website may be published without an additional security review.
- Product tests and documented demonstrations are not substitutes for real external-user validation.

File issues at https://github.com/Roy0x/eeksha/issues with the step, error text, platform, and non-sensitive input characteristics. Do not publicly attach private farm imagery or sensitive data.

## Reimport an existing annotation ZIP into Workspace

When an Eeksha polygon or brush export exists, open `http://127.0.0.1:8022/workspace`, select the exact original RGB and depth PNG files and the exported ZIP, then choose **Import labels from ZIP**. The server verifies the exported mask's SHA-256 and that both original source files match the QA report. It restores the mask and the previously recorded Eeksha calibration **in memory**, without rewriting your original files. Next choose **Check input readiness** and **Process real scene**. You do not need to extract `labels.png` by hand. A source mismatch is rejected, even if the pictures have identical dimensions. Source matching does not verify semantic correctness, depth geometry, or independently reviewed ground truth.
