"""Standalone browser viewer for an exported Eeksha semantic point cloud."""
from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np


def generate_viewer(npz_file: Path, qa_file: Path, html_file: Path, limit: int = 12000) -> None:
    """Write a self-contained HTML preview; never modifies source coordinates."""
    if limit < 1:
        raise ValueError("Point limit must be positive")
    with np.load(npz_file) as bundle:
        xyz = bundle["xyz"]
        rgb = bundle["rgb"]
        labels = bundle["labels"]
    if xyz.ndim != 2 or xyz.shape[1] != 3 or rgb.shape != xyz.shape or labels.shape != (len(xyz),):
        raise ValueError("Invalid point cloud array shapes")
    if not np.isfinite(xyz).all():
        raise ValueError("Point cloud contains non-finite coordinates")
    indices = np.linspace(0, len(xyz) - 1, min(len(xyz), limit), dtype=int) if len(xyz) else np.array([], dtype=int)
    points = [[round(float(v), 5) for v in xyz[i]] + [int(labels[i])] for i in indices]
    report = json.loads(qa_file.read_text(encoding="utf-8"))
    counts = report["class_counts"]
    summary = (f"{report['points']:,} points · {report['depth_coverage'] * 100:.1f}% valid depth · "
               f"{counts['crop']:,} crop · {counts['weed']:,} weed · {counts['soil']:,} soil")
    page = TEMPLATE.replace("__POINTS__", json.dumps(points, separators=(",", ":")))
    page = page.replace("__SUMMARY__", html.escape(summary))
    page = page.replace("__SOURCE__", html.escape("SYNTHETIC TEST SCENE" if report.get("synthetic_demo") else "USER-SUPPLIED DATA — ACCURACY UNVERIFIED"))
    page = page.replace("__WARNINGS__", html.escape(" | ".join(report.get("limitations", []))))
    html_file.write_text(page, encoding="utf-8")


TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eeksha — 3D Semantic Scene</title><style>
*{box-sizing:border-box}body{margin:0;background:#0b1115;color:#ecf3ed;font:15px system-ui,Segoe UI,sans-serif}
header{padding:22px 28px;border-bottom:1px solid #23322d;display:flex;justify-content:space-between;gap:15px;align-items:center;flex-wrap:wrap}
h1{margin:0;font-size:26px;letter-spacing:-1px}small{color:#92a79c}.tag{background:#1c382c;color:#9ce9b4;border-radius:99px;padding:8px 12px;font-size:12px;font-weight:700}
main{display:grid;grid-template-columns:1fr 275px;gap:16px;padding:18px;max-width:1500px;margin:auto}
.panel{background:#121b20;border:1px solid #25362f;border-radius:14px;overflow:hidden}canvas{display:block;width:100%;height:min(72vh,720px);touch-action:none;cursor:grab}
aside{padding:22px}h2{font-size:15px;margin:0 0 18px}.control{margin-bottom:22px}label{display:block;margin-bottom:10px;color:#b1c2b7}
input[type=range]{width:100%;accent-color:#7ad79d}.row{display:flex;gap:10px;align-items:center;margin-bottom:13px}input[type=checkbox]{accent-color:#75d79b}
button{border:1px solid #466957;background:#1b3128;color:#c4f5d2;border-radius:7px;padding:10px 12px;cursor:pointer;width:100%}
.stats{margin:13px 0 18px;line-height:1.65;color:#b1c2b7}footer{padding:0 25px 24px;color:#8ea199;font-size:12px}
@media(max-width:850px){main{grid-template-columns:1fr}canvas{height:55vh}}
</style></head><body>
<header><div><h1>EEK<span style="color:#7ad79d">SHA</span><small> / Semantic 3D Explorer</small></h1><small>Drag to rotate · Scroll to zoom · Toggle classes</small></div><span class="tag">__SOURCE__</span></header>
<main><section class="panel"><canvas id="view" aria-label="Interactive projected 3D point cloud"></canvas></section>
<aside class="panel"><h2>SCENE INFORMATION</h2><div class="stats">__SUMMARY__</div>
<div class="control"><label>VISIBLE CLASSES</label><div class="row"><input id="soil" type="checkbox" checked><label for="soil" style="margin:0">Soil · brown</label></div>
<div class="row"><input id="crop" type="checkbox" checked><label for="crop" style="margin:0">Crop · green</label></div>
<div class="row"><input id="weed" type="checkbox" checked><label for="weed" style="margin:0">Weed · orange</label></div>
<div class="row"><input id="unknown" type="checkbox" checked><label for="unknown" style="margin:0">Unknown · grey</label></div></div>
<div class="control"><label for="size">POINT SIZE</label><input id="size" type="range" min="1" max="7" step="0.5" value="2"></div>
<button id="reset">Reset view</button><p class="stats">Points shown: <span id="shown"></span></p></aside></main>
<footer>Quality warnings: __WARNINGS__</footer>
<script>
const points=__POINTS__;
const canvas=document.getElementById('view'),ctx=canvas.getContext('2d');
const ids=['unknown','soil','crop','weed'];const color=['#9faab4','#80634a','#6fc681','#f1a24a'];
let yaw=-.5,pitch=.5,zoom=1,drag=false,px=0,py=0;
const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),zs=points.map(p=>p[2]);
const mid=[(Math.min(...xs)+Math.max(...xs))/2,(Math.min(...ys)+Math.max(...ys))/2,(Math.min(...zs)+Math.max(...zs))/2];
const spread=Math.max(0.001,Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys),Math.max(...zs)-Math.min(...zs));
function draw(){
 const r=canvas.getBoundingClientRect(),dpi=Math.min(devicePixelRatio||1,2);canvas.width=Math.max(1,Math.round(r.width*dpi));canvas.height=Math.max(1,Math.round(r.height*dpi));
 ctx.setTransform(dpi,0,0,dpi,0,0);const w=r.width,h=r.height;ctx.clearRect(0,0,w,h);ctx.fillStyle='#0b151a';ctx.fillRect(0,0,w,h);
 const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch),scale=Math.min(w,h)*.7/spread*zoom;
 const visible=points.filter(p=>document.getElementById(ids[p[3]])?.checked);
 const projected=visible.map(p=>{const x=p[0]-mid[0],y=p[1]-mid[1],z=p[2]-mid[2];const a=x*cy-z*sy,b=x*sy+z*cy;return [w/2+a*scale,h/2+(y*cp-b*sp)*scale,b*cp+y*sp,p[3]]});
 projected.sort((a,b)=>b[2]-a[2]);const rad=Number(document.getElementById('size').value);for(const p of projected){ctx.fillStyle=color[p[3]];ctx.fillRect(p[0],p[1],rad,rad)}
 document.getElementById('shown').textContent=visible.length.toLocaleString()+' / '+points.length.toLocaleString();
}
canvas.addEventListener('pointerdown',e=>{drag=true;px=e.clientX;py=e.clientY;canvas.setPointerCapture(e.pointerId)});
canvas.addEventListener('pointerup',()=>drag=false);canvas.addEventListener('pointermove',e=>{if(!drag)return;yaw+=(e.clientX-px)*.008;pitch=Math.max(-1.5,Math.min(1.5,pitch+(e.clientY-py)*.008));px=e.clientX;py=e.clientY;draw()});
canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.15,Math.min(12,zoom*Math.exp(-e.deltaY*.001)));draw()},{passive:false});
document.querySelectorAll('input').forEach(el=>el.addEventListener('input',draw));
document.getElementById('reset').onclick=()=>{yaw=-.5;pitch=.5;zoom=1;draw()};window.addEventListener('resize',draw);draw();
</script></body></html>'''
