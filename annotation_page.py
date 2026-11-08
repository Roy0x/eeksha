"""Self-contained local manual annotation interface."""

PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eeksha · Human 3D Annotation</title>
<style>
*{box-sizing:border-box}body{font:15px system-ui;background:#0e1714;color:#e4eee5;margin:0}
header{border-bottom:1px solid #334c3d;padding:18px 26px}h1{margin:0;font-size:25px}
main{display:grid;grid-template-columns:320px minmax(0,1fr);gap:20px;padding:20px;max-width:1450px;margin:auto}
.panel{background:#182621;border:1px solid #365341;border-radius:12px;padding:20px}
input,select,button{width:100%;padding:10px;margin:7px 0 13px;background:#10201a;color:#e4eee5;border:1px solid #4b7057;border-radius:6px}
button{background:#95e5a3;color:#142719;font-weight:700;cursor:pointer}button.secondary{background:#385746;color:white}
canvas{width:100%;max-width:640px;height:auto;display:block;cursor:crosshair;touch-action:none;user-select:none}
#canvas-wrap{position:relative;line-height:0}p{line-height:1.5;color:#afc3b4}a{color:#a1f4b4}
#preview{width:100%;height:650px;border:0;background:#0c1410;display:none}#status{white-space:pre-wrap}
@media(max-width:850px){main{grid-template-columns:1fr}}
</style></head><body>
<header><h1>EEK<span style="color:#95e5a3">SHA</span> / Human RGB-D Annotation</h1></header>
<main><section class="panel"><h2>1 · Load scene</h2>
<label>RGB PNG<input id="rgb" type="file" accept="image/png"></label>
<label>Matching 16-bit depth PNG<input id="depth" type="file" accept="image/png"></label>
<label>Published camera_intrinsics.json<input id="calibration" type="file" accept=".json,application/json"></label>
<h2>2 · Draw annotation</h2><p><strong>Hold and drag</strong> to trace a smooth object boundary (mouse, touch, or pen). You can also click individual corners for precision. Release, then finish the polygon. Zoom your browser for easier tracing.</p>
<select id="kind"><option value="4">Broccoli head</option><option value="5">Broccoli leaf</option><option value="1">Soil</option><option value="2">Crop (other)</option><option value="3">Weed</option></select>
<button id="finish">Finish polygon</button><button class="secondary" id="undo">Undo last vertex</button>
<button class="secondary" id="remove">Remove last polygon</button><p id="count">0 polygons</p>
<h2>3 · Export labeled 3D</h2><button id="export">Generate cloud and download pack</button>
<p id="status">Choose an RGB image to begin.</p><a href="/">Return to main Eeksha</a>
</section><section class="panel"><h2>RGB scene and explicit annotations</h2>
<div id="canvas-wrap"><canvas id="canvas" width="640" height="480"></canvas></div>
<p>Colored regions are hand-drawn annotations. Unmarked pixels remain UNKNOWN. This is not AI inference or verified ground truth.</p>
<iframe id="preview" title="3D point cloud"></iframe>
</section></main>
<script>
const input=document.getElementById('rgb'),canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d');
const status=document.getElementById('status'),count=document.getElementById('count');
let photo=null,polygons=[],points=[],pointerDown=false,pointerId=null,renderPending=false;
const palette={1:'#ba8553',2:'#e7cb47',3:'#e95757',4:'#59daf2',5:'#7fee7a'};
function scheduleDraw(){if(renderPending)return;renderPending=true;requestAnimationFrame(()=>{renderPending=false;draw();});}
function draw(){ctx.clearRect(0,0,canvas.width,canvas.height);if(photo)ctx.drawImage(photo,0,0);
for(const poly of polygons){ctx.fillStyle=palette[poly.class_id]+'88';ctx.strokeStyle=palette[poly.class_id];
ctx.beginPath();poly.vertices.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.fill();ctx.stroke();}
ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.stroke();
for(const [x,y] of points){ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();}
count.textContent=polygons.length+' completed polygons · '+points.length+' pending vertices';}
input.onchange=()=>{if(!input.files.length)return;const url=URL.createObjectURL(input.files[0]);const img=new Image();
img.onload=()=>{URL.revokeObjectURL(url);photo=img;canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;polygons=[];points=[];draw();status.textContent='Image loaded. Hold and drag to trace a boundary.';};img.src=url;};
// Canvas coordinates are computed from the actual rendered image, without object-fit letterboxing.
function imagePoint(e){const r=canvas.getBoundingClientRect();return [
Math.min(canvas.width-1,Math.max(0,Math.round((e.clientX-r.left)*canvas.width/r.width))),
Math.min(canvas.height-1,Math.max(0,Math.round((e.clientY-r.top)*canvas.height/r.height)))];}
function distance(a,b){return Math.hypot(a[0]-b[0],a[1]-b[1]);}
function addPoint(point,minimum){if(!points.length||distance(points[points.length-1],point)>=minimum){points.push(point);scheduleDraw();}}
// Ramer-Douglas-Peucker: preserve shape while limiting polygon size and render/export work.
function simplify(path,tolerance){if(path.length<3)return path.slice();const keep=new Set([0,path.length-1]);
const stack=[[0,path.length-1]];while(stack.length){const [a,b]=stack.pop();let best=-1,far=0;
const start=path[a],end=path[b],dx=end[0]-start[0],dy=end[1]-start[1],den=dx*dx+dy*dy;
for(let i=a+1;i<b;i++){const p=path[i];const t=den?Math.max(0,Math.min(1,((p[0]-start[0])*dx+(p[1]-start[1])*dy)/den)):0;
const d=Math.hypot(p[0]-start[0]-t*dx,p[1]-start[1]-t*dy);if(d>far){far=d;best=i;}}
if(far>tolerance&&best>=0){keep.add(best);stack.push([a,best],[best,b]);}}
return [...keep].sort((a,b)=>a-b).map(i=>path[i]);}
canvas.addEventListener('pointerdown',e=>{if(!photo||pointerDown)return;e.preventDefault();pointerDown=true;pointerId=e.pointerId;
canvas.setPointerCapture(e.pointerId);addPoint(imagePoint(e),0);});
canvas.addEventListener('pointermove',e=>{if(!pointerDown||e.pointerId!==pointerId)return;e.preventDefault();
const p=imagePoint(e);addPoint(p,1.5);});
function endStroke(e){if(!pointerDown||e.pointerId!==pointerId)return;pointerDown=false;pointerId=null;
if(e.type==='pointerup')addPoint(imagePoint(e),1);scheduleDraw();}
canvas.addEventListener('pointerup',endStroke);canvas.addEventListener('pointercancel',endStroke);
document.getElementById('finish').onclick=()=>{if(pointerDown){status.textContent='Release the pointer first.';return;}
const optimized=simplify(points,1.5);const unique=new Set(optimized.map(p=>p.join(',')));
if(unique.size<3){status.textContent='Trace a closed region with at least three distinct points.';return;}
if(optimized.length>450){status.textContent='Boundary is too complex. Trace a smaller region.';return;}
polygons.push({class_id:Number(document.getElementById('kind').value),vertices:optimized});points=[];scheduleDraw();};
document.getElementById('undo').onclick=()=>{if(!pointerDown){points.pop();scheduleDraw();}};
document.getElementById('remove').onclick=()=>{if(!pointerDown){if(points.length){points=[];}else{polygons.pop();}scheduleDraw();}};
document.getElementById('export').onclick=async()=>{if(!photo||!polygons.length||points.length){status.textContent='Finish all polygons and choose input files.';return;}
const depth=document.getElementById('depth').files[0],calibration=document.getElementById('calibration').files[0];
if(!depth||!calibration){status.textContent='Depth PNG and calibration JSON are required.';return;}
let body=new FormData();body.append('rgb',input.files[0]);body.append('depth',depth);body.append('calibration',calibration);
body.append('annotations',JSON.stringify(polygons));status.textContent='Generating calibrated labeled cloud...';
try{const response=await fetch('/annotate',{method:'POST',body});const result=await response.json();
if(!response.ok)throw Error(result.error||'Export failed');
status.textContent=result.report.points.toLocaleString()+' valid 3D points; annotation not independently reviewed.\nDownload the dataset pack below.';
let link=document.createElement('a');link.href='/download/'+result.id;link.textContent='Download annotation and 3D ZIP';
link.style.display='block';link.style.marginTop='12px';status.after(link);
const viewer=document.getElementById('preview');viewer.src='/viewer/'+result.id;viewer.style.display='block';}
catch(error){status.textContent='Error: '+error.message;}};
</script></body></html>'''
