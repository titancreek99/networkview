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


PAGE = """<!doctype html><html><head><title>NetworkView Logs</title>
<style>body{font-family:system-ui,sans-serif;max-width:1050px;margin:1rem auto;padding:0 1rem}
select,input{padding:.4rem;margin:.2rem}
table{width:100%;border-collapse:collapse;font-size:.85rem}
td,th{border-bottom:1px solid #eee;padding:4px 6px;text-align:left;vertical-align:top}
.ERROR{color:#dc2626}.INFO{color:#111}tr:hover{background:#f7f7ff}
code{background:#f0f0f5;padding:1px 4px;border-radius:4px}</style></head><body>
<h1>NetworkView — Logs</h1>
<div>App: <select id="app"></select>
Level: <select id="level"><option value="">any</option><option>INFO</option><option>ERROR</option></select>
Search: <input id="q" placeholder="e.g. upstream_error">
<button onclick="load()">refresh</button>
<label><input type="checkbox" id="auto" checked> auto</label></div>
<table><thead><tr><th>time</th><th>app/host</th><th>lvl</th><th>event</th><th>details</th></tr></thead>
<tbody id="rows"></tbody></table>
<script>
function apps(){return fetch('/api/apps').then(r=>r.json()).then(a=>{
  const s=document.getElementById('app');const cur=s.value;
  s.innerHTML=a.map(x=>`<option>${x}</option>`).join('');if(cur)s.value=cur;});}
function load(){
  const p=new URLSearchParams({app:document.getElementById('app').value,
    level:document.getElementById('level').value,q:document.getElementById('q').value,limit:200});
  fetch('/api/logs?'+p).then(r=>r.json()).then(d=>{
    document.getElementById('rows').innerHTML=d.records.slice().reverse().map(r=>{
      const det=Object.assign({},r);['ts','app','host','level','event'].forEach(k=>delete det[k]);
      return `<tr class="${r.level||''}"><td>${(r.ts||'').slice(11,23)}</td>
        <td>${r.app||''}<br><small>${(r.host||'').slice(0,10)}</small></td>
        <td>${r.level||''}</td><td><code>${r.event||r.msg||''}</code></td>
        <td><small>${JSON.stringify(det)}</small></td></tr>`;}).join('');});}
apps();load();
setInterval(()=>{apps();if(document.getElementById('auto').checked)load();},2500);
</script></body></html>"""


@app.get("/")
def index():
    return render_template_string(PAGE)


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
