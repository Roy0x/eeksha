"""Local-only Eeksha browser workflow. Not a production web server."""
from __future__ import annotations

import io
import os
import base64
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
import numpy as np

from flask import Flask, Response, abort, render_template_string, request, send_file
from PIL import UnidentifiedImageError, Image
from annotation import record_annotations
from annotation_page import PAGE as ANNOTATOR_PAGE
from real_field_demo import convert_intrinsics
from review import compare_exports, make_rgb_overlay
from review_page import PAGE as REVIEW_PAGE
from correction_page import PAGE as CORRECTION_PAGE
from workspace_page import PAGE as WORKSPACE_PAGE
from input_preflight import inspect_inputs
from qa_compare import compare_qa
from correction import apply_strokes, verify_source, load_exported_mask
from correction_quality import summarize_correction
from review import load_annotation
from eeksha import make_demo, process
from viewer import generate_viewer
from we3ds import inspect_we3ds

APP = Flask(__name__)
APP.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024
FILES = {"rgb": "rgb.png", "depth": "depth.png", "labels": "labels.png", "calibration": "calibration.json"}
RUNS: dict[str, dict] = {}


def build_run(folder: Path, synthetic: bool) -> tuple[dict, str, bytes]:
    output = folder / "out"
    report = process(*(folder / name for name in FILES.values()), output)
    report["synthetic_demo"] = synthetic
    (output / "qa_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    generate_viewer(output / "semantic_cloud.npz", output / "qa_report.json", output / "viewer.html")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in output.iterdir():
            if path.name != "viewer.html":
                zipped.write(path, path.name)
    return report, (output / "viewer.html").read_text(encoding="utf-8"), archive.getvalue()


@APP.get("/")
def index():
    return render_template_string(PAGE)


@APP.get("/workspace")
def workspace():
    """Unifies the existing local dataset workflows; no remote storage."""
    return Response(WORKSPACE_PAGE, mimetype="text/html")


@APP.post("/preflight")
def preflight():
    """Check source structure without processing or retaining uploaded files."""
    fields = ("rgb", "depth", "labels", "calibration")
    if any(key not in request.files or not request.files[key].filename for key in fields):
        return {"error": "Upload RGB, depth, labels and calibration"}, 400
    try:
        payload = {key: request.files[key].read() for key in fields}
        return inspect_inputs(payload["rgb"], payload["depth"], payload["labels"], payload["calibration"])
    except ValueError as exc:
        return {"error": str(exc), "ready": False}, 422


@APP.post("/workspace/compare-qa")
def workspace_compare_qa():
    """Compare source-matched baseline and corrected Eeksha export ZIPs."""
    if any(name not in request.files or not request.files[name].filename for name in ("before", "after")):
        return {"error": "Select baseline and corrected Eeksha ZIPs"}, 400
    try:
        return compare_qa(request.files["before"].read(), request.files["after"].read())
    except (ValueError, OSError, TypeError, KeyError) as error:
        return {"error": str(error)}, 422


@APP.post("/workspace/import-annotation")
def workspace_import_annotation():
    """Import a verified Eeksha ZIP mask for the user's original RGB/depth files."""
    if any(k not in request.files or not request.files[k].filename for k in ("archive", "rgb", "depth")):
        return {"error": "Choose annotation ZIP and the exact original RGB and depth PNGs"}, 400
    archive = request.files["archive"].read()
    rgb = request.files["rgb"].read()
    depth = request.files["depth"].read()
    if not rgb or not depth or len(rgb) > 20 * 1024 * 1024 or len(depth) > 20 * 1024 * 1024:
        return {"error": "RGB and depth files must be nonempty and each under 20 MB"}, 422
    try:
        labels, report = load_exported_mask(archive)
        verify_source(rgb, report["sources"]["rgb"], "RGB")
        verify_source(depth, report["sources"]["depth"], "Depth")
        with Image.open(io.BytesIO(rgb)) as rgb_image:
            if rgb_image.format != "PNG" or rgb_image.mode not in ("RGB", "RGBA"):
                raise ValueError("Original RGB must be a PNG image")
            if rgb_image.size != (labels.shape[1], labels.shape[0]):
                raise ValueError("Imported labels do not match RGB dimensions")
        with Image.open(io.BytesIO(depth)) as depth_image:
            if depth_image.format != "PNG" or depth_image.size != (labels.shape[1], labels.shape[0]):
                raise ValueError("Imported labels do not match depth PNG dimensions")
        label_buf = io.BytesIO()
        Image.fromarray(labels.astype(np.uint8), mode="L").save(label_buf, format="PNG")
        calibration = report["calibration"]
        if not all(k in calibration for k in ("fx", "fy", "cx", "cy", "depth_scale", "depth_type")):
            raise ValueError("Dataset QA calibration is missing required fields")
        # This is source-matched structural reimport, not annotation certification.
        return {
            "labels_png_base64": base64.b64encode(label_buf.getvalue()).decode("ascii"),
            "calibration": calibration,
            "review_status": report.get("annotation_review", "UNVERIFIED"),
            "warning": "Source hashes verified; semantic correctness and geometry remain unverified",
        }
    except (ValueError, KeyError, TypeError, OSError, UnidentifiedImageError) as exc:
        return {"error": str(exc)}, 422


@APP.post("/calibration/convert")
def calibration_convert():
    """Normalize supported published RGB camera metadata without guessing values."""
    upload = request.files.get("calibration")
    if not upload or not upload.filename:
        return {"error": "Select a source camera_intrinsics.json file"}, 400
    raw = upload.read()
    if not raw or len(raw) > 1024 * 1024:
        return {"error": "Calibration JSON must be nonempty and at most 1 MB"}, 422
    try:
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "camera_intrinsics.json"
            destination = Path(folder) / "calibration.json"
            source.write_bytes(raw)
            converted = convert_intrinsics(source, destination)
            if not all(np.isfinite(converted[key]) for key in ("fx", "fy", "cx", "cy", "depth_scale")):
                raise ValueError("Converted camera intrinsics contain nonfinite values")
            if converted["fx"] <= 0 or converted["fy"] <= 0:
                raise ValueError("Converted focal lengths must be positive")
        return {
            "calibration": converted,
            "source_type": "SUPPORTED_MENDELEY_RGB_INTRINSICS",
            "warning": "Converted from source metadata, not independently measured or geometry-validated",
        }
    except (ValueError, KeyError, TypeError, OverflowError, UnicodeError, json.JSONDecodeError, OSError) as exc:
        return {"error": f"Cannot convert source calibration: {exc}"}, 422


@APP.get("/annotator")
def annotator():
    return Response(ANNOTATOR_PAGE, mimetype="text/html")


@APP.get("/correct")
def correction_page():
    return Response(CORRECTION_PAGE, mimetype="text/html")


@APP.post("/correction/prepare")
def correction_prepare():
    if "rgb" not in request.files or not request.files["rgb"].filename:
        return {"error": "Upload an RGB PNG"}, 400
    try:
        rgb = request.files["rgb"].read()
        with Image.open(io.BytesIO(rgb)) as image:
            if image.format != "PNG" or image.mode not in ("RGB", "RGBA") or image.width * image.height > 4_000_000:
                raise ValueError("RGB must be an RGB/RGBA PNG with at most 4 million pixels")
            width, height = image.size
        archive_upload = request.files.get('archive')
        if archive_upload and archive_upload.filename:
            original, prior_report = load_exported_mask(archive_upload.read())
            verify_source(rgb, prior_report['sources']['rgb'], 'RGB')
            if original.shape != (height, width):
                raise ValueError('Mask dimensions disagree with RGB')
        else:
            original = np.zeros((height, width), dtype=np.uint8)
        mask = io.BytesIO()
        Image.fromarray(original.astype("uint8")).save(mask, format="PNG")
    except (ValueError, OSError, UnidentifiedImageError) as exc:
        return {"error": str(exc)}, 422
    return {"width": original.shape[1], "height": original.shape[0], "resumed": bool(archive_upload and archive_upload.filename),
            "verified_rgb_base64": base64.b64encode(rgb).decode("ascii"),
            "mask_preview_base64": base64.b64encode(mask.getvalue()).decode("ascii")}


@APP.post("/correction/export")
def correction_export():
    from uuid import uuid4
    if any(name not in request.files or not request.files[name].filename
           for name in ("rgb", "depth", "calibration")):
        return {"error": "Upload RGB, depth, and camera intrinsics"}, 400
    try:
        strokes = json.loads(request.form.get("strokes", "null"))
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            rgb = request.files["rgb"].read()
            depth = request.files["depth"].read()
            with Image.open(io.BytesIO(rgb)) as image:
                if image.format != "PNG" or image.mode not in ("RGB", "RGBA") or image.width * image.height > 4_000_000:
                    raise ValueError("RGB must be an RGB/RGBA PNG with at most 4 million pixels")
                width, height = image.size
            archive_upload = request.files.get("archive")
            archive = archive_upload.read() if archive_upload and archive_upload.filename else None
            if archive is not None:
                original_labels, original_qa = load_exported_mask(archive)
                verify_source(rgb, original_qa["sources"]["rgb"], "RGB")
                verify_source(depth, original_qa["sources"]["depth"], "Depth")
                labels, audit = apply_strokes(original_labels, strokes, request.form.get("reviewer", ""))
                audit.update({"provenance": "human_brush_correction",
                              "review_status": "HUMAN_REVIEWED_NOT_GROUND_TRUTH",
                              "original_annotation_sha256": hashlib.sha256(archive).hexdigest(),
                              "original_label_sha256": original_qa['sources']['labels']['sha256']})
            else:
                original_labels = np.zeros((height, width), dtype=np.uint8)
                labels, audit = apply_strokes(original_labels, strokes, request.form.get("reviewer", ""))
            (folder / "rgb.png").write_bytes(rgb)
            (folder / "depth.png").write_bytes(depth)
            (folder / "camera_intrinsics.json").write_bytes(request.files["calibration"].read())
            convert_intrinsics(folder / "camera_intrinsics.json", folder / "calibration.json")
            labels.save(folder / "labels.png")
            report, viewer_html, standard_archive = build_run(folder, synthetic=False)
            if archive is not None and report["calibration"] != original_qa["calibration"]:
                raise ValueError("Camera calibration does not match original annotation")
            with Image.open(folder / "depth.png") as depth_image:
                quality = summarize_correction(original_labels, labels, np.asarray(depth_image),
                                               float(report["calibration"]["depth_scale"]),
                                               float(report["max_depth_m"]))
            report["annotation_provenance"] = audit["provenance"]
            report["annotation_review"] = audit["review_status"]
            report["labels_predicted_by_ai"] = False
            report["correction_quality"] = quality
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zipped:
                with zipfile.ZipFile(io.BytesIO(standard_archive)) as original:
                    for filename in original.namelist():
                        zipped.writestr(filename, json.dumps(report, indent=2) if filename == "qa_report.json"
                                        else original.read(filename))
                zipped.write(folder / "labels.png", "labels.png")
                zipped.write(folder / "camera_intrinsics.json", "camera_intrinsics.json")
                zipped.writestr("correction_audit.json", json.dumps(audit, indent=2))
                zipped.writestr("correction_quality.json", json.dumps(quality, indent=2))
                if archive is not None:
                    zipped.writestr("original_annotation.zip", archive)
    except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError, UnidentifiedImageError) as exc:
        return {"error": str(exc)}, 422
    token = uuid4().hex
    RUNS.clear()
    RUNS[token] = {"report": report, "viewer": viewer_html, "archive": output.getvalue()}
    return {"id": token, "changed_pixels": audit["changed_pixels"], "quality": quality,
            "review_status": audit["review_status"], "ground_truth_verified": False}


@APP.route("/review", methods=["GET", "POST"])
def annotation_review():
    if request.method == "GET":
        return Response(REVIEW_PAGE, mimetype="text/html")
    if any(field not in request.files or not request.files[field].filename
           for field in ("first", "second")):
        return {"error": "Upload both Eeksha annotation ZIP exports"}, 400
    try:
        summary, preview = compare_exports(request.files["first"].read(),
                                           request.files["second"].read())
        overlay = {}
        if "rgb" in request.files and request.files["rgb"].filename:
            rgb, transparent = make_rgb_overlay(request.files["rgb"].read(), preview, summary)
            overlay = {"verified_rgb_base64": base64.b64encode(rgb).decode("ascii"),
                       "transparent_overlay_base64": base64.b64encode(transparent).decode("ascii")}
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}, 422
    return {"summary": summary,
            "disagreement_preview_base64": base64.b64encode(preview).decode("ascii"), **overlay}


@APP.post("/annotate")
def annotated_upload():
    """Reconstruct only human-drawn class polygons; never synthesize labels."""
    from uuid import uuid4

    if any(name not in request.files or not request.files[name].filename
           for name in ("rgb", "depth", "calibration")):
        return {"error": "Upload RGB, matching depth, and calibration"}, 400
    try:
        polygons = json.loads(request.form.get("annotations", "null"))
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for field, filename in (("rgb", "rgb.png"), ("depth", "depth.png"),
                                    ("calibration", "camera_intrinsics.json")):
                data = request.files[field].read()
                if not data:
                    raise ValueError(f"Empty file: {field}")
                (folder / filename).write_bytes(data)
            with Image.open(folder / "rgb.png") as rgb_image:
                record = record_annotations(folder, polygons, *rgb_image.size)
            convert_intrinsics(folder / "camera_intrinsics.json", folder / "calibration.json")
            report, viewer_html, archive = build_run(folder, synthetic=False)
            report["annotation_provenance"] = record["provenance"]
            report["annotation_review"] = record["review_status"]
            report["labels_predicted_by_ai"] = False
            # Include human annotation source and input calibration in the export.
            out_bytes = io.BytesIO()
            with zipfile.ZipFile(out_bytes, "w", compression=zipfile.ZIP_DEFLATED) as target:
                with zipfile.ZipFile(io.BytesIO(archive)) as original:
                    for filename in original.namelist():
                        if filename == "qa_report.json":
                            target.writestr(filename, json.dumps(report, indent=2))
                        else:
                            target.writestr(filename, original.read(filename))
                for filename in ("annotations.json", "labels.png", "camera_intrinsics.json"):
                    target.write(folder / filename, filename)
    except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError, UnidentifiedImageError) as exc:
        return {"error": str(exc)}, 422
    token = uuid4().hex
    RUNS.clear()
    RUNS[token] = {"report": report, "viewer": viewer_html, "archive": out_bytes.getvalue()}
    return {"id": token, "report": report}


@APP.post("/process")
def upload():
    from uuid import uuid4

    demo = request.form.get("demo") == "true"
    if not demo and any(name not in request.files or not request.files[name].filename for name in FILES):
        return {"error": "Upload all four files: RGB, depth, labels, calibration"}, 400
    try:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            if demo:
                make_demo(folder)
            else:
                for field, filename in FILES.items():
                    data = request.files[field].read()
                    if not data:
                        raise ValueError(f"Empty file: {field}")
                    (folder / filename).write_bytes(data)
            report, viewer, archive = build_run(folder, demo)
    except (ValueError, OSError, json.JSONDecodeError, UnidentifiedImageError) as exc:
        return {"error": str(exc)}, 422
    token = uuid4().hex
    # Small, bounded local prototype cache; replaced on a new run.
    RUNS.clear()
    RUNS[token] = {"report": report, "viewer": viewer, "archive": archive}
    return {"id": token, "report": report}


@APP.post("/we3ds")
def we3ds_upload():
    from uuid import uuid4
    fields = ("rgb", "depth", "labels")
    if any(field not in request.files or not request.files[field].filename for field in fields):
        return {"error": "Upload RGB, refined depth, and ground truth files"}, 400
    try:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for field in fields:
                data = request.files[field].read()
                if not data:
                    raise ValueError(f"Empty WE3DS file: {field}")
                (root / f"{field}.png").write_bytes(data)
            output = root / "out"
            report = inspect_we3ds(*(root / f"{field}.png" for field in fields), output)
            previews = {
                key: "data:image/png;base64," + base64.b64encode((output / name).read_bytes()).decode("ascii")
                for key, name in (("rgb", "rgb_preview.png"), ("depth", "depth_preview.png"),
                                  ("labels", "semantic_overlay.png"))
            }
            archive_buffer = io.BytesIO()
            with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in output.iterdir():
                    archive.write(path, path.name)
    except (ValueError, OSError, UnidentifiedImageError) as exc:
        return {"error": str(exc)}, 422
    token = uuid4().hex
    RUNS.clear()
    RUNS[token] = {"report": report, "previews": previews, "archive": archive_buffer.getvalue()}
    return {"id": token, "report": report}


@APP.get("/we3ds-preview/<token>")
def we3ds_preview(token: str):
    if token not in RUNS or "previews" not in RUNS[token]:
        abort(404)
    return render_template_string("""<!doctype html><html><head><meta charset="utf-8"><title>Eeksha WE3DS review</title>
<style>body{background:#0c1214;color:#e9f1eb;font:16px system-ui;padding:24px}img{width:100%;height:auto}section{max-width:1100px;margin:auto}h1{color:#89e3a7}p{color:#b9ccbf}</style></head>
<body><section><h1>WE3DS · Real RGB-D validation</h1><p>2D input reviewed. Metric 3D geometry is blocked until authentic camera intrinsics are available.</p>
<h2>RGB</h2><img src="{{ images.rgb }}" alt="RGB input"><h2>Depth contrast preview (not raw depth units)</h2><img src="{{ images.depth }}" alt="Depth preview">
<h2>Semantic overlay</h2><img src="{{ images.labels }}" alt="Class-mask overlay"></section></body></html>""", images=RUNS[token]["previews"])


@APP.get("/viewer/<token>")
def viewer(token: str):
    if token not in RUNS:
        abort(404)
    return Response(RUNS[token]["viewer"], mimetype="text/html")


@APP.get("/download/<token>")
def download(token: str):
    if token not in RUNS:
        abort(404)
    return send_file(io.BytesIO(RUNS[token]["archive"]), mimetype="application/zip",
                     as_attachment=True, download_name="eeksha-dataset.zip")


PAGE = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eeksha · Agricultural Spatial Data</title><style>
*{box-sizing:border-box}body{margin:0;background:#0c1214;color:#e9f1eb;font:15px system-ui,Segoe UI,sans-serif}header{border-bottom:1px solid #253930;padding:20px 28px;display:flex;justify-content:space-between;align-items:center}h1{margin:0;font-size:27px;letter-spacing:-1px}h1 span{color:#89e3a7}small{color:#93a79a}main{max-width:1450px;margin:auto;padding:22px;display:grid;grid-template-columns:350px 1fr;gap:18px}.panel{background:#14201d;border:1px solid #2b4438;border-radius:14px;padding:22px}h2{font-size:18px;margin:0 0 18px}label{display:block;color:#a7c2af;margin:14px 0 7px}input[type=file]{width:100%;border:1px dashed #426451;border-radius:8px;padding:10px;background:#101915;color:#cce4d4}button,.download{border:0;border-radius:8px;background:#8ae6ab;color:#0b2417;font-weight:800;padding:13px 16px;cursor:pointer;width:100%;display:block;text-align:center;text-decoration:none;margin-top:16px}button.secondary{background:#2b4938;color:#d4f1dd}iframe{width:100%;height:650px;border:0;border-radius:10px;background:#0c1417}.muted{color:#9cb2a6;line-height:1.6}.error{color:#ffad9d}#metrics{padding:12px 0;line-height:1.6}#result{display:none}@media(max-width:900px){main{grid-template-columns:1fr}iframe{height:510px}}</style></head><body>
<header><h1>EEK<span>SHA</span> <small> / Agricultural Spatial Data</small></h1><small>LOCAL MVP · NOT A FIELD VALIDATION</small></header><main><section class="panel"><h2>01 / Input scene</h2><p class="muted">Use calibrated, aligned RGB-D imagery and class-ID masks. Files stay on your computer; this tool only listens on localhost.</p><a class="download" href="/workspace">Open dataset workspace →</a><a class="download" href="/annotator">Open human polygon annotator →</a><a class="download" href="/correct">Correct existing annotations →</a>
<form id="form"><label>RGB image (PNG)</label><input type="file" name="rgb" accept="image/png"><label>Depth image (PNG, numeric)</label><input type="file" name="depth" accept="image/png"><label>Class mask (PNG, 0–3)</label><input type="file" name="labels" accept="image/png"><label>Camera calibration (JSON)</label><input type="file" name="calibration" accept="application/json,.json"><button type="submit">Process real input</button></form>
<button class="secondary" id="demo">Load synthetic example</button><hr style="border-color:#365447;margin-top:25px"><h2>WE3DS / Real dataset inspector</h2><p class="muted">Upload the matched RGB, refined depth (16-bit), and ground-truth masks. No calibration guesses; 3D export stays blocked.</p><form id="we3ds-form"><label>WE3DS RGB PNG</label><input name="rgb" type="file" accept="image/png" required><label>WE3DS depth_refined PNG</label><input name="depth" type="file" accept="image/png" required><label>WE3DS ground_truth PNG</label><input name="labels" type="file" accept="image/png" required><button type="submit">Inspect WE3DS sample</button></form><p id="message" class="muted">No scene processed yet.</p><div id="result"><h2>03 / Quality & export</h2><div id="metrics"></div><a class="download" id="download">Download dataset ZIP</a><p class="muted">Structural checks do not establish geometric accuracy or safe robot operation.</p></div></section>
<section class="panel"><h2>02 / Semantic 3D viewer</h2><div id="blank" class="muted">Process a sample to inspect its reconstructed point cloud.</div><iframe id="viewer" title="3D point cloud viewer" hidden></iframe></section></main>
<script>const msg=document.getElementById('message');async function run(data){msg.textContent='Processing...';msg.className='muted';try{const res=await fetch('/process',{method:'POST',body:data});const payload=await res.json();if(!res.ok)throw Error(payload.error||'Processing failed');const q=payload.report;msg.textContent=q.synthetic_demo?'SYNTHETIC TEST DATA — not field evidence':'USER-SUPPLIED DATA — calibration accuracy not independently verified';document.getElementById('metrics').textContent=q.points.toLocaleString()+' valid points · '+(q.depth_coverage*100).toFixed(1)+'% depth coverage';const viewer=document.getElementById('viewer');viewer.src='/viewer/'+payload.id;viewer.hidden=false;document.getElementById('blank').hidden=true;document.getElementById('download').href='/download/'+payload.id;document.getElementById('result').style.display='block'}catch(err){msg.textContent=err.message;msg.className='error'}}document.getElementById('form').onsubmit=e=>{e.preventDefault();run(new FormData(e.currentTarget))};document.getElementById('demo').onclick=()=>{let d=new FormData();d.append('demo','true');run(d)};document.getElementById('we3ds-form').onsubmit=async e=>{e.preventDefault();msg.textContent='Inspecting real dataset...';try{let res=await fetch('/we3ds',{method:'POST',body:new FormData(e.currentTarget)});let d=await res.json();if(!res.ok)throw Error(d.error||'Inspection failed');msg.textContent='WE3DS 2D INPUT VALID · 3D BLOCKED: MISSING CAMERA INTRINSICS';let q=d.report;document.getElementById('metrics').textContent='Depth '+q.depth_min_m.toFixed(3)+'–'+q.depth_max_m.toFixed(3)+' m · '+Object.entries(q.class_counts).map(([k,v])=>k+': '+v.toLocaleString()).join(', ');document.getElementById('viewer').src='/we3ds-preview/'+d.id;document.getElementById('viewer').hidden=false;document.getElementById('blank').hidden=true;document.getElementById('download').href='/download/'+d.id;document.getElementById('result').style.display='block'}catch(err){msg.textContent=err.message;msg.className='error'}};</script></body></html>'''


if __name__ == "__main__":
    APP.run(host="127.0.0.1", port=int(os.environ.get("EEKSHA_PORT", "8022")), debug=False)
