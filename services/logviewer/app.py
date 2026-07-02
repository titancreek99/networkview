"""
logviewer - aggregated log console.

Every service writes JSON-line logs to the shared /logs volume via appkit.
This app lists those log files and tails/filters them so you can watch the
whole request path light up (frontend -> middleware -> backend -> db) and
correlate it with what you see in the packet sniffer.
"""
import glob
import json
import os
import sys

from flask import jsonify, render_template_string, request

sys.path.insert(0, "/app")
from common.appkit import make_app
from common.theme import BASE_CSS, topbar

app, log = make_app()
LOG_DIR = os.environ.get("LOG_DIR", "/logs")


def list_apps():
    return sorted(os.path.basename(p)[:-4]
                  for p in glob.glob(os.path.join(LOG_DIR, "*.log")))


def tail_json(path, limit, level=None, contains=None):
    try:
        with open(path, errors="replace") as fh:
            lines = fh.readlines()[-2000:]
    except OSError:
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            rec = {"msg": line}
        if level and rec.get("level") != level:
            continue
        if contains and contains.lower() not in line.lower():
            continue
        out.append(rec)
    return out[-limit:]


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NetworkView — Logs</title><style>{{ css|safe }}
td.det{color:var(--muted);font-family:var(--mono);font-size:11.5px}
tr.ERROR td{color:var(--err)}
.lvl{font-size:11px;font-weight:700;padding:1px 7px;border-radius:6px;border:1px solid var(--border-2)}
.lvl.INFO{color:var(--info)} .lvl.ERROR{color:var(--err);border-color:var(--err)}
.ev{font-family:var(--mono);font-size:12px}
</style></head><body>
{{ topbar|safe }}
<div class="wrap">
  <section class="hero"><h1>Log <span class="grad">Viewer</span></h1>
    <p>Live JSON logs from every service. Pick an app and watch one request light
       up the whole path.</p></section>

  <div class="panel">
    <div class="toolbar">
      <label>App</label><select id="app"></select>
      <label>Level</label>
      <select id="level"><option value="">any</option><option>INFO</option><option>ERROR</option></select>
      <input id="q" placeholder="search e.g. upstream_error" style="min-width:200px">
      <button class="btn" onclick="load()">↻ Refresh</button>
      <label class="badge"><input type="checkbox" id="auto" checked> auto</label>
      <span class="badge muted" id="count" style="margin-left:auto"></span>
    </div>
    <div style="overflow:auto;max-height:66vh">
      <table><thead><tr><th>time</th><th>app / host</th><th>lvl</th><th>event</th><th>details</th></tr></thead>
      <tbody id="rows"></tbody></table>
    </div>
  </div>
  <div style="height:40px"></div>
</div>
<script>
function apps(){return fetch('/api/apps').then(r=>r.json()).then(a=>{
  const s=document.getElementById('app');const cur=s.value;
  s.innerHTML=a.map(x=>`<option>${x}</option>`).join('');if(cur)s.value=cur;});}
function esc(s){return (s+'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function load(){
  const p=new URLSearchParams({app:document.getElementById('app').value,
    level:document.getElementById('level').value,q:document.getElementById('q').value,limit:200});
  fetch('/api/logs?'+p).then(r=>r.json()).then(d=>{
    document.getElementById('count').textContent=(d.count||0)+' lines';
    document.getElementById('rows').innerHTML=d.records.slice().reverse().map(r=>{
      const det=Object.assign({},r);['ts','app','host','level','event'].forEach(k=>delete det[k]);
      return `<tr class="${r.level||''}"><td class="faint">${esc((r.ts||'').slice(11,23))}</td>
        <td>${esc(r.app||'')}<br><small class="faint">${esc((r.host||'').slice(0,10))}</small></td>
        <td><span class="lvl ${r.level||''}">${esc(r.level||'')}</span></td>
        <td class="ev">${esc(r.event||r.msg||'')}</td>
        <td class="det">${esc(JSON.stringify(det))}</td></tr>`;}).join('');});}
apps();load();
setInterval(()=>{apps();if(document.getElementById('auto').checked)load();},2500);
</script></body></html>"""


@app.get("/")
def index():
    return render_template_string(PAGE, css=BASE_CSS, topbar=topbar("logs"))


@app.get("/api/apps")
def api_apps():
    return jsonify(list_apps())


@app.get("/api/logs")
def api_logs():
    name = request.args.get("app", "")
    if not name or "/" in name or ".." in name:
        return jsonify(records=[])
    path = os.path.join(LOG_DIR, f"{name}.log")
    recs = tail_json(path, int(request.args.get("limit", 200)),
                     request.args.get("level") or None,
                     request.args.get("q") or None)
    return jsonify(app=name, count=len(recs), records=recs)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), threaded=True)
