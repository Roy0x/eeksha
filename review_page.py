"""Local side-by-side annotation comparison page."""

PAGE = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eeksha / Annotation QA</title><style>
*{box-sizing:border-box}body{margin:0;background:#0c1712;color:#e6f0e8;font:15px system-ui}
main{max-width:1100px;margin:26px auto;padding:24px}section{background:#18291e;border:1px solid #385645;border-radius:12px;padding:24px;margin-bottom:20px}
h1{font-size:28px}h2{font-size:18px}p{line-height:1.6;color:#b5c9ba}input{display:block;margin:12px 0 20px}
button{padding:13px 22px;background:#a0edb6;border:0;border-radius:6px;color:#132b1d;font-weight:700;cursor:pointer}
img{max-width:640px;width:100%;image-rendering:pixelated;border:1px solid #385645}pre{white-space:pre-wrap;overflow-wrap:anywhere}
.warn{color:#ffd998}a{color:#a0edb6}</style></head><body><main>
<h1>EEK<span style="color:#a0edb6">SHA</span> / Annotation quality comparison</h1>
<p>Compare two manual annotation ZIP exports of the <strong>same RGB-D scene</strong>. They should be drawn independently. Matching labels are not proof of accuracy; a reviewer must adjudicate disagreements.</p>
<section><h2>Load annotation exports</h2><form id="form">
<label>Annotation A<input name="first" type="file" accept=".zip" required></label>
<label>Annotation B<input name="second" type="file" accept=".zip" required></label>
<button type="submit">Compare masks</button></form><p id="status">No comparison run yet.</p></section>
<section id="result" hidden><h2>Agreement map</h2>
<p><span style="color:#41af6e">Green: same class</span> · <span style="color:#ff46be">Pink: A only</span> · <span style="color:#ffbe2d">Orange: B only</span> · <span style="color:#ff4141">Red: different classes</span> · Black: both unknown</p>
<img id="image" alt="Class agreement and disagreement map"><h2>Detailed metrics</h2><pre id="metrics"></pre>
<p class="warn">NEEDS HUMAN ADJUDICATION. This tool cannot certify labels as ground truth.</p></section>
<a href="/annotator">Back to annotator</a></main>
<script>
document.getElementById('form').onsubmit=async e=>{e.preventDefault();const status=document.getElementById('status');
status.textContent='Comparing annotation masks...';document.getElementById('result').hidden=true;
try{const r=await fetch('/review',{method:'POST',body:new FormData(e.currentTarget)});
const data=await r.json();if(!r.ok)throw Error(data.error||'Review failed');
document.getElementById('image').src='data:image/png;base64,'+data.disagreement_preview_base64;
document.getElementById('metrics').textContent=JSON.stringify(data.summary,null,2);
document.getElementById('result').hidden=false;status.textContent='Compared. Human review remains required.';
}catch(err){status.textContent=err.message;}};
</script></body></html>'''
