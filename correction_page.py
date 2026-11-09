"""Lightweight browser brush editor for human annotation adjudication."""

PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eeksha / Correct annotation</title><style>
*{box-sizing:border-box}body{background:#101a15;color:#e9f4eb;font:15px system-ui;margin:0}
header{padding:16px 24px;border-bottom:1px solid #365444}main{display:grid;grid-template-columns:310px minmax(0,1fr);gap:18px;padding:20px}
section{background:#192b21;border:1px solid #395b46;border-radius:12px;padding:20px}label{display:block;margin-top:12px}
input,select,button{display:block;width:100%;padding:9px;margin:6px 0 12px;background:#102017;color:white;border:1px solid #54725d;border-radius:6px}
button{background:#a1e9b0;color:#14281c;font-weight:bold;cursor:pointer}.minor{background:#35533f;color:#fff}
#viewport{overflow:auto;max-height:75vh;border:1px solid #456a50;background:#07140c}
#stage{position:relative;width:640px;height:480px;line-height:0;transform-origin:top left}
#photo,#paint{position:absolute;inset:0;width:100%;height:100%}#paint{touch-action:none;cursor:crosshair}
#photo[hidden]{display:none}#image-status{font-size:13px;color:#e0c89a}
#status{white-space:pre-wrap;color:#c5dcc9}p{color:#c1d3c6;line-height:1.5}a{color:#a1e9b0}
#qa{white-space:pre-wrap;color:#d4ead9;line-height:1.7;border-left:3px solid #a1e9b0;padding-left:12px}
#cloud{width:100%;height:530px;border:1px solid #456a50;margin-top:18px;background:#091316}
@media(max-width:850px){main{grid-template-columns:1fr}}
</style></head><body><header><h1>EEK<span style="color:#a1e9b0">SHA</span> / Human correction</h1></header><main>
<section><h2>1 · Open original annotations</h2>
<label>Original annotation ZIP<input id="archive" type="file" accept=".zip"></label>
<label>Exact source RGB PNG<input id="rgb" type="file" accept="image/png"></label>
<button id="load">Load for correction</button><h2>2 · Correct pixels</h2>
<label>Tool / semantic class<select id="kind"><option value="4">Broccoli head</option><option value="5">Broccoli leaf</option><option value="1">Soil</option><option value="2">Other crop</option><option value="3">Weed</option><option value="0">Eraser / unknown</option></select></label>
<label>Brush radius (source pixels) <output id="radius-value">8</output><input id="radius" type="range" min="1" max="40" value="8"></label>
<label>Zoom <output id="zoom-value">100%</output><input id="zoom" type="range" min="50" max="400" step="25" value="100"></label>
<button class="minor" id="undo">Undo stroke</button><button class="minor" id="redo">Redo stroke</button>
<h2>3 · Export corrected 3D</h2><p>The next two files are needed only for 3D export, not to load the image.</p>
<label>Exact source depth PNG<input id="depth" type="file" accept="image/png"></label>
<label>Original camera_intrinsics.json<input id="calibration" type="file" accept=".json"></label>
<label>Reviewer identifier<input id="reviewer" maxlength="80" placeholder="Your name or reviewer ID"></label>
<button id="export">Export reviewed 3D dataset</button><p id="status" role="status">Load the original ZIP and source files.</p>
<h3>Correction quality report</h3><div id="qa">Export to see before/after metrics.</div>
<a href="/review">Comparison</a> · <a href="/annotator">Annotation</a>
</section><section><h2>Source RGB + editable class mask</h2><p id="image-status" role="status">Choose an RGB PNG to preview it. Annotation editing stays locked until ZIP verification.</p><div id="viewport"><div id="stage"><img id="photo" alt="Source RGB preview" hidden><canvas id="paint" width="640" height="480"></canvas></div></div>
<p>Corrections are human-made. Eraser restores UNKNOWN. Undo/redo and pan by scrolling when zoomed. A reviewed export is not independently verified ground truth.</p>
<iframe id="cloud" title="Corrected 3D point-cloud preview" hidden></iframe></section></main>
<script>
const $=id=>document.getElementById(id),canvas=$('paint'),ctx=canvas.getContext('2d',{willReadFrequently:true});
let width=0,height=0,original=null,strokes=[],redo=[],current=null,active=null,rect=null,previewUrl=null,selectionVersion=0,colors={0:[0,0,0,0],1:[186,133,83,140],2:[231,203,71,140],3:[233,87,87,140],4:[89,218,242,140],5:[127,238,122,140]};
const source=(name)=>$(name).files[0];function readyForLoad(){return source('archive')&&source('rgb');}
function readyForExport(){return ['archive','rgb','depth','calibration'].every(id=>source(id));}
function lockEditing(){original=null;strokes=[];redo=[];ctx.clearRect(0,0,canvas.width,canvas.height);$('cloud').hidden=true;}
function previewRGB(){selectionVersion++;lockEditing();const file=source('rgb'),photo=$('photo');
if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null;}photo.hidden=true;photo.removeAttribute('src');
if(!file){$('image-status').textContent='Choose an RGB PNG to preview it.';return;}
previewUrl=URL.createObjectURL(file);const version=selectionVersion;
photo.onload=()=>{if(version!==selectionVersion)return;width=photo.naturalWidth;height=photo.naturalHeight;
canvas.width=width;canvas.height=height;$('zoom').value='100';$('zoom-value').textContent='100%';
$('stage').style.width=width+'px';$('stage').style.height=height+'px';photo.hidden=false;
$('image-status').textContent='RGB preview loaded locally. Click Load for correction to verify the ZIP and unlock editing.';};
photo.onerror=()=>{if(version!==selectionVersion)return;photo.hidden=true;$('image-status').textContent='RGB file could not be decoded. Select a valid PNG.';};
photo.src=previewUrl;}
$('rgb').addEventListener('change',previewRGB);
$('archive').addEventListener('change',()=>{selectionVersion++;lockEditing();$('image-status').textContent='Original ZIP changed. Click Load for correction to verify it against the RGB.';});
function point(e){const r=rect||canvas.getBoundingClientRect();return [Math.max(0,Math.min(width-1,Math.round((e.clientX-r.left)*width/r.width))),Math.max(0,Math.min(height-1,Math.round((e.clientY-r.top)*height/r.height)))];}
function mark(path,color,radius){ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=radius*2;ctx.beginPath();path.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.stroke();for(const [x,y] of path){ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);ctx.fill();}}
function replay(){if(!original)return;ctx.putImageData(original,0,0);for(const s of strokes){const c=colors[s.class_id];mark(s.points,s.class_id===0?'rgba(0,0,0,1)':`rgba(${c[0]},${c[1]},${c[2]},0.55)`,s.radius);}}
function drawStroke(s){if(s.class_id===0){ // Erase annotation overlay, not the source photograph.
replay();return;}const c=colors[s.class_id];mark(s.points,`rgba(${c[0]},${c[1]},${c[2]},0.55)`,s.radius);}
// Overlay rendering is rebuilt from class-ID mask and history; it does not determine exported labels.
function repaint(){if(!original)return;ctx.putImageData(original,0,0);for(const s of strokes){const c=colors[s.class_id];ctx.globalCompositeOperation=s.class_id===0?'destination-out':'source-over';mark(s.points,s.class_id===0?'#000':`rgba(${c[0]},${c[1]},${c[2]},0.7)`,s.radius);}ctx.globalCompositeOperation='source-over';}
function showSegment(path){const c=colors[current.class_id];ctx.globalCompositeOperation=current.class_id===0?'destination-out':'source-over';mark(path,current.class_id===0?'#000':`rgba(${c[0]},${c[1]},${c[2]},0.7)`,current.radius);ctx.globalCompositeOperation='source-over';}
function begin(e){if(!original||active!==null)return;e.preventDefault();active=e.pointerId;rect=canvas.getBoundingClientRect();canvas.setPointerCapture(active);current={class_id:Number($('kind').value),radius:Number($('radius').value),points:[point(e)]};showSegment(current.points);}
function move(e){if(active!==e.pointerId)return;e.preventDefault();const samples=e.getCoalescedEvents?.()||[];for(const sample of samples.length?samples:[e]){const p=point(sample),last=current.points.at(-1);if(Math.hypot(p[0]-last[0],p[1]-last[1])>=1&&current.points.length<4000){current.points.push(p);showSegment([last,p]);}}}
function end(e){if(active!==e.pointerId)return;strokes.push(current);redo=[];current=null;active=null;rect=null;repaint();$('status').textContent=strokes.length+' correction strokes. Review before export.';}
canvas.addEventListener('pointerdown',begin);canvas.addEventListener('pointermove',move);canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);
$('undo').onclick=()=>{if(active===null&&strokes.length){redo.push(strokes.pop());repaint();}};
$('redo').onclick=()=>{if(active===null&&redo.length){strokes.push(redo.pop());repaint();}};
$('radius').oninput=()=>{$('radius-value').textContent=$('radius').value};
$('zoom').oninput=()=>{const scale=Number($('zoom').value)/100;$('stage').style.width=(width*scale)+'px';$('stage').style.height=(height*scale)+'px';$('zoom-value').textContent=$('zoom').value+'%';};
$('load').onclick=async()=>{if(!readyForLoad()){$('status').textContent='Choose the original annotation ZIP and its matching RGB PNG, then click Load.';return;}
const version=selectionVersion;lockEditing();const body=new FormData();body.append('archive',source('archive'));body.append('rgb',source('rgb'));$('status').textContent='Validating source provenance...';
try{const response=await fetch('/correction/prepare',{method:'POST',body});const payload=await response.json();if(version!==selectionVersion)return;
if(!response.ok)throw Error(payload.error||'Source validation failed');
if($('photo').hidden)throw Error('RGB image did not decode locally. Please reselect the PNG.');
if(width!==payload.width||height!==payload.height)throw Error('RGB dimensions do not match the annotation ZIP');
const mask=new Image();mask.onerror=()=>{$('status').textContent='Annotation mask could not be decoded.';};
mask.onload=()=>{if(version!==selectionVersion)return;try{const tmp=document.createElement('canvas');tmp.width=width;tmp.height=height;
const t=tmp.getContext('2d');t.drawImage(mask,0,0);const pixels=t.getImageData(0,0,width,height);const rgba=ctx.createImageData(width,height);
for(let i=0;i<width*height;i++){const c=colors[pixels.data[4*i]]||colors[0];rgba.data.set(c,i*4);}
original=rgba;strokes=[];redo=[];repaint();$('status').textContent='Source verified. Brush corrections unlocked.';
$('image-status').textContent='VERIFIED RGB + ANNOTATION — editing unlocked.';
}catch(err){$('status').textContent='Mask preview error: '+err.message;}};
mask.src='data:image/png;base64,'+payload.mask_preview_base64;
}catch(err){$('status').textContent='Cannot unlock editing: '+err.message;
$('image-status').textContent='RGB preview only — ZIP verification failed. '+err.message;}};
$('export').onclick=async()=>{if(!original){$('status').textContent='Load the annotation ZIP and RGB first.';return;}
if(!strokes.length){$('status').textContent='Make at least one correction before exporting.';return;}
if(!readyForExport()){$('status').textContent='To export 3D, add matching depth PNG and camera_intrinsics.json.';return;}
const body=new FormData();for(const id of ['archive','rgb','depth','calibration'])body.append(id,source(id));body.append('strokes',JSON.stringify(strokes));body.append('reviewer',$('reviewer').value);
$('status').textContent='Rebuilding corrected 3D data...';try{const response=await fetch('/correction/export',{method:'POST',body});const data=await response.json();if(!response.ok)throw Error(data.error);
const link=document.createElement('a');link.href='/download/'+data.id;link.textContent='Download human-reviewed 3D ZIP';link.style.display='block';link.style.color='#a1e9b0';$('status').replaceChildren(document.createTextNode(data.changed_pixels+' mask pixels changed. Reviewed, not ground truth. '),link);
const q=data.quality,head=q.classes.broccoli_head;
$('qa').textContent=`Edited image pixels: ${q.changed_pixels.toLocaleString()}\nEdits with valid 3D depth: ${q.changed_pixels_with_valid_depth.toLocaleString()}\nEdits without valid depth: ${q.changed_pixels_without_valid_depth.toLocaleString()}\nBroccoli-head pixels: ${head.before_pixels.toLocaleString()} → ${head.after_pixels.toLocaleString()}\nBroccoli-head valid 3D points: ${head.before_valid_3d_points.toLocaleString()} → ${head.after_valid_3d_points.toLocaleString()}\nStatus: ${q.status} — NOT VERIFIED GROUND TRUTH`;
const cloud=$('cloud');cloud.src='/viewer/'+data.id;cloud.hidden=false;
}catch(err){$('status').textContent='Error: '+err.message;}};
</script></body></html>'''
