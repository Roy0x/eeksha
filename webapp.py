"""Local-only Eeksha browser workflow. Not a production web server."""
from __future__ import annotations

import io
import base64
import json
import tempfile
import zipfile
from pathlib import Path

from flask import Flask, Response, abort, render_template_string, request, send_file
from PIL import UnidentifiedImageError
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
<header><h1>EEK<span>SHA</span> <small> / Agricultural Spatial Data</small></h1><small>LOCAL MVP · NOT A FIELD VALIDATION</small></header><main><section class="panel"><h2>01 / Input scene</h2><p class="muted">Use calibrated, aligned RGB-D imagery and class-ID masks. Files stay on your computer; this tool only listens on localhost.</p>
<form id="form"><label>RGB image (PNG)</label><input type="file" name="rgb" accept="image/png"><label>Depth image (PNG, numeric)</label><input type="file" name="depth" accept="image/png"><label>Class mask (PNG, 0–3)</label><input type="file" name="labels" accept="image/png"><label>Camera calibration (JSON)</label><input type="file" name="calibration" accept="application/json,.json"><button type="submit">Process real input</button></form>
<button class="secondary" id="demo">Load synthetic example</button><hr style="border-color:#365447;margin-top:25px"><h2>WE3DS / Real dataset inspector</h2><p class="muted">Upload the matched RGB, refined depth (16-bit), and ground-truth masks. No calibration guesses; 3D export stays blocked.</p><form id="we3ds-form"><label>WE3DS RGB PNG</label><input name="rgb" type="file" accept="image/png" required><label>WE3DS depth_refined PNG</label><input name="depth" type="file" accept="image/png" required><label>WE3DS ground_truth PNG</label><input name="labels" type="file" accept="image/png" required><button type="submit">Inspect WE3DS sample</button></form><p id="message" class="muted">No scene processed yet.</p><div id="result"><h2>03 / Quality & export</h2><div id="metrics"></div><a class="download" id="download">Download dataset ZIP</a><p class="muted">Structural checks do not establish geometric accuracy or safe robot operation.</p></div></section>
<section class="panel"><h2>02 / Semantic 3D viewer</h2><div id="blank" class="muted">Process a sample to inspect its reconstructed point cloud.</div><iframe id="viewer" title="3D point cloud viewer" hidden></iframe></section></main>
<script>const msg=document.getElementById('message');async function run(data){msg.textContent='Processing...';msg.className='muted';try{const res=await fetch('/process',{method:'POST',body:data});const payload=await res.json();if(!res.ok)throw Error(payload.error||'Processing failed');const q=payload.report;msg.textContent=q.synthetic_demo?'SYNTHETIC TEST DATA — not field evidence':'USER-SUPPLIED DATA — calibration accuracy not independently verified';document.getElementById('metrics').textContent=q.points.toLocaleString()+' valid points · '+(q.depth_coverage*100).toFixed(1)+'% depth coverage';const viewer=document.getElementById('viewer');viewer.src='/viewer/'+payload.id;viewer.hidden=false;document.getElementById('blank').hidden=true;document.getElementById('download').href='/download/'+payload.id;document.getElementById('result').style.display='block'}catch(err){msg.textContent=err.message;msg.className='error'}}document.getElementById('form').onsubmit=e=>{e.preventDefault();run(new FormData(e.currentTarget))};document.getElementById('demo').onclick=()=>{let d=new FormData();d.append('demo','true');run(d)};document.getElementById('we3ds-form').onsubmit=async e=>{e.preventDefault();msg.textContent='Inspecting real dataset...';try{let res=await fetch('/we3ds',{method:'POST',body:new FormData(e.currentTarget)});let d=await res.json();if(!res.ok)throw Error(d.error||'Inspection failed');msg.textContent='WE3DS 2D INPUT VALID · 3D BLOCKED: MISSING CAMERA INTRINSICS';let q=d.report;document.getElementById('metrics').textContent='Depth '+q.depth_min_m.toFixed(3)+'–'+q.depth_max_m.toFixed(3)+' m · '+Object.entries(q.class_counts).map(([k,v])=>k+': '+v.toLocaleString()).join(', ');document.getElementById('viewer').src='/we3ds-preview/'+d.id;document.getElementById('viewer').hidden=false;document.getElementById('blank').hidden=true;document.getElementById('download').href='/download/'+d.id;document.getElementById('result').style.display='block'}catch(err){msg.textContent=err.message;msg.className='error'}};</script></body></html>'''


if __name__ == "__main__":
    APP.run(host="127.0.0.1", port=8012, debug=False)
