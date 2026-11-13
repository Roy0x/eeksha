"""Local browser dataset workspace: orchestration UI for existing Eeksha endpoints.

No persistence, no cloud sync, no claim of validated ground truth.
"""
PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eeksha / Dataset Workspace</title>
<style>
:root{color-scheme:dark;--bg:#0c1210;--panel:#141f1a;--line:#294337;--muted:#a4baab;--green:#a1edb9;--text:#edf7ef}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,Segoe UI,sans-serif}
a{color:var(--green);text-decoration:none}a:hover{text-decoration:underline}
header{display:flex;justify-content:space-between;align-items:center;padding:20px 28px;border-bottom:1px solid var(--line);gap:12px}
.brand{font-size:21px;font-weight:850;letter-spacing:-1px}.brand span{color:var(--green)}
header nav{display:flex;gap:20px;flex-wrap:wrap}.eyebrow{font-size:11px;text-transform:uppercase;color:var(--muted);letter-spacing:1.7px;font-weight:750}
main{max-width:1550px;margin:0 auto;padding:27px}.top{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:25px}
h1{font-size:36px;margin:5px 0;letter-spacing:-1.4px}p{color:var(--muted);margin:8px 0}
.layout{display:grid;grid-template-columns:minmax(300px,370px) minmax(0,1fr);gap:18px}
.panel{border:1px solid var(--line);background:var(--panel);border-radius:16px;padding:21px;min-width:0}
h2{font-size:17px;margin:0 0 12px}h3{font-size:14px;margin:0 0 9px}.steps{display:grid;gap:14px}
label{display:block;font-size:12px;color:var(--muted);margin:13px 0 6px}
input[type=file]{width:100%;font:inherit;color:var(--text);padding:10px;border:1px dashed #466754;border-radius:9px;background:#101a15}
input[type=file]::file-selector-button{background:#355543;color:white;border:0;border-radius:6px;padding:6px 10px;margin-right:10px;cursor:pointer}
button,.action{border:1px solid #5a9e73;border-radius:9px;background:var(--green);color:#102819;padding:11px 15px;font:inherit;font-weight:800;cursor:pointer}
button:disabled{opacity:.5;cursor:not-allowed}.action{display:inline-block;text-align:center}
.secondary{background:#223a2d;color:#e6faec;border-color:#446a53}
.buttons{display:flex;gap:9px;flex-wrap:wrap;margin-top:15px}.buttons>*{flex:1}
.hint{font-size:12px;color:#b7c8b9}.notice{background:#273523;border:1px solid #4c6442;color:#e1eacb;padding:10px 12px;border-radius:9px;font-size:12px}
.stage{display:grid;grid-template-columns:1fr 1fr;gap:13px}.tile{border:1px solid var(--line);border-radius:12px;background:#0e1914;padding:13px;min-height:100px}
.big{font-size:25px;font-weight:800;letter-spacing:-.6px}.small{font-size:12px;color:var(--muted)}
.preview{width:100%;max-height:250px;object-fit:contain;border-radius:9px;background:#09110d;margin-top:12px}
.frame{width:100%;height:480px;border:1px solid #345343;border-radius:12px;background:#08120d}
.empty{display:flex;justify-content:center;align-items:center;min-height:300px;text-align:center;color:var(--muted);border:1px dashed #476251;border-radius:12px;padding:20px}
#visual[hidden],#download[hidden],#image[hidden]{display:none}
#status{padding:10px 12px;border-radius:8px;border:1px solid var(--line);margin:13px 0;white-space:pre-wrap;color:#bce9c8}
#status.error{color:#ffc7bb;border-color:#9b574d}
#status.loading{color:#f1e5a5;border-color:#85723f}
.tools{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.tool{border:1px solid var(--line);border-radius:10px;padding:13px;background:#0e1914}
.tool strong{display:block;margin-bottom:7px}.tool p{font-size:12px;margin:0 0 10px}
@media(max-width:980px){.layout{grid-template-columns:1fr}.tools{grid-template-columns:1fr 1fr}}
@media(max-width:620px){header,.top{flex-direction:column;align-items:start}.tools,.stage{grid-template-columns:1fr}main{padding:14px}h1{font-size:28px}}
</style></head>
<body><header><div class="brand">EEK<span>SHA</span> <span class="eyebrow"> / Workspace v0.8</span></div>
<nav><a href="/">Original processor</a><a href="/annotator">Annotator</a><a href="/correct">Corrections</a><a href="/review">Review</a></nav></header>
<main><div class="top"><div><div class="eyebrow">Agricultural spatial data</div><h1>Dataset workspace</h1>
<p>One place to inspect input readiness, run calibrated 3D processing, and open review tools.</p></div><div class="notice">LOCAL ONLY · No cloud storage · No accuracy certification</div></div>
<div class="layout"><div class="panel"><h2>01 / Import a scene</h2>
<p>Upload aligned, distortion-corrected RGB, depth, semantic labels and recorded calibration.</p>
<form id="scene-form">
<label for="rgb">RGB image · PNG</label><input id="rgb" name="rgb" type="file" accept=".png,image/png" required>
<label for="depth">Depth map · PNG</label><input id="depth" name="depth" type="file" accept=".png,image/png" required>
<label for="labels">Semantic class mask · PNG, IDs 0–5</label><input id="labels" name="labels" type="file" accept=".png,image/png" required>
<label for="calibration">Camera calibration · JSON</label><input id="calibration" name="calibration" type="file" accept=".json,application/json" required>
<div class="buttons"><button type="submit" id="process">Process real scene</button><button type="button" class="secondary" id="demo">Synthetic demo</button></div>
</form>
<div role="status" aria-live="polite" id="status">Select all four files, or explore the synthetic demo.</div>
<p class="hint">Calibration must include fx, fy, cx, cy, depth_scale and depth_type. Missing calibration cannot be inferred.</p>
<img class="preview" id="image" hidden alt="Selected RGB image preview">
</div>
<div class="steps">
<div class="panel"><h2>02 / Quality overview</h2>
<div class="stage"><div class="tile"><div class="eyebrow">Valid 3D points</div><div class="big" id="points">—</div></div>
<div class="tile"><div class="eyebrow">Depth coverage</div><div class="big" id="coverage">—</div></div>
<div class="tile"><div class="eyebrow">Input provenance</div><div id="provenance">Not processed</div><div class="small" id="source">No dataset selected</div></div>
<div class="tile"><div class="eyebrow">Reported status</div><div id="qa">Awaiting input</div><div class="small">Structural QA, not ground truth</div></div></div>
<div id="classes" class="hint" style="margin-top:13px">Class counts will appear after processing.</div>
<div class="buttons"><a id="download" hidden class="action" href="#">Download export ZIP</a></div>
</div>
<div class="panel"><h2>03 / Semantic 3D preview</h2>
<div class="empty" id="empty">Process a scene to inspect its generated point cloud.</div>
<iframe id="visual" class="frame" title="Interactive semantic point cloud" hidden sandbox="allow-scripts"></iframe>
<p class="hint">Preview may downsample points. Export retains the full valid-depth cloud.</p>
</div>
<div class="panel"><h2>04 / Human labeling workflow</h2><div class="tools">
<div class="tool"><strong>Polygon annotation</strong><p>Trace human-defined crop, soil and weed regions.</p><a href="/annotator">Open annotator →</a></div>
<div class="tool"><strong>Brush correction</strong><p>Resume exported labels, correct pixels, and re-export.</p><a href="/correct">Open editor →</a></div>
<div class="tool"><strong>Disagreement review</strong><p>Compare two independent annotation ZIPs.</p><a href="/review">Open review →</a></div>
</div></div>
</div></div>
</main>
<script>
const $=id=>document.getElementById(id);
let currentPreview=null;
$('rgb').addEventListener('change',()=>{
  if(currentPreview){URL.revokeObjectURL(currentPreview);currentPreview=null;}
  const file=$('rgb').files[0];
  if(file && file.type==='image/png'){currentPreview=URL.createObjectURL(file);$('image').src=currentPreview;$('image').hidden=false;}
  else{$('image').hidden=true;$('image').removeAttribute('src');}
});
function status(message,kind=''){$('status').textContent=message;$('status').className=kind;}
function reset(){$('points').textContent='—';$('coverage').textContent='—';$('qa').textContent='Awaiting input';$('classes').textContent='';$('download').hidden=true;$('visual').hidden=true;$('visual').removeAttribute('src');$('empty').hidden=false;}
async function processScene(payload,synthetic){
  reset();$('process').disabled=true;$('demo').disabled=true;status('Processing scene locally…','loading');
  try{
    const response=await fetch('/process',{method:'POST',body:payload});
    let result=await response.json();
    if(!response.ok)throw new Error(result.error||'Processing failed');
    const q=result.report||{};
    if(typeof q.points!=='number'||typeof q.depth_coverage!=='number'||!result.id)throw new Error('Incomplete server response');
    $('points').textContent=q.points.toLocaleString();
    $('coverage').textContent=(q.depth_coverage*100).toFixed(1)+'%';
    $('provenance').textContent=q.synthetic_demo?'Synthetic test pixels':'User-provided inputs';
    $('source').textContent=q.synthetic_demo?'Not collected in a field':'Geometry and labels are not independently validated';
    $('qa').textContent=q.status||'Unknown';
    $('classes').textContent='Class counts: '+Object.entries(q.class_counts||{}).map(([name,count])=>name+' '+Number(count).toLocaleString()).join(' · ');
    $('download').href='/download/'+encodeURIComponent(result.id);$('download').hidden=false;
    $('visual').src='/viewer/'+encodeURIComponent(result.id);$('visual').hidden=false;$('empty').hidden=true;
    status(synthetic?'Synthetic demonstration completed. Not field evidence.':'Processing completed. Structural quality only; verify labels and geometry independently.');
  }catch(error){status(error.message||'Unknown error','error');}
  finally{$('process').disabled=false;$('demo').disabled=false;}
}
$('scene-form').addEventListener('submit',e=>{e.preventDefault();processScene(new FormData(e.currentTarget),false);});
$('demo').addEventListener('click',()=>{let data=new FormData();data.set('demo','true');processScene(data,true);});
</script></body></html>'''
