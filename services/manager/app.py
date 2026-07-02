"""
manager - the control plane / "ops console" for the whole lab.

  * Change the ACTIVE BACKEND VERSION (blue/green: v1 <-> v2) live.
  * Inject FAULTS (latency, error rate) into the backend.
  * Generate RANDOMIZED TRAFFIC through the edge LB, mixing HTTP, HTTPS/TLS1.3
    and HTTPS/TLS1.2 - which gives the packet sniffer something to capture and
    the LB stats something to distribute.

All state lives in the shared control-store JSON that the app services read.
"""
import os
import random
import sys
import threading
import time

import requests
from flask import jsonify, render_template_string, request

sys.path.insert(0, "/app")
from common.appkit import make_app, ControlStore

app, log = make_app()
control = ControlStore()

CA_BUNDLE = os.environ.get("CA_BUNDLE", "/certs/ca-chain.crt")
# The three ways to reach the same app through the edge LTM.
TARGETS = {
    "http":    "http://lb-edge:80/orders",
    "https13": "https://lb-edge:443/orders",
    "https12": "https://lb-edge:8443/orders",
}

_stats = {"sent": 0, "ok": 0, "err": 0, "by_proto": {}}


def _fire(proto: str):
    url = TARGETS[proto]
    try:
        if url.startswith("https"):
            r = requests.get(url, timeout=6, verify=CA_BUNDLE)
        else:
            r = requests.get(url, timeout=6)
        _stats["sent"] += 1
        _stats["by_proto"][proto] = _stats["by_proto"].get(proto, 0) + 1
        if r.ok:
            _stats["ok"] += 1
        else:
            _stats["err"] += 1
    except requests.RequestException as exc:
        _stats["sent"] += 1
        _stats["err"] += 1
        log.error("traffic error", extra={"event": "traffic_err",
                  "upstream": url, "extra": {"err": str(exc)[:120]}})


def traffic_loop():
    """Background generator; obeys traffic.running / rps / mix from control store."""
    while True:
        cfg = control.read().get("traffic", {})
        if not cfg.get("running"):
            time.sleep(1)
            continue
        rps = max(1, int(cfg.get("rps", 2)))
        mix = cfg.get("mix") or ["https13", "http", "https12"]
        proto = random.choice([p for p in mix if p in TARGETS] or ["http"])
        threading.Thread(target=_fire, args=(proto,), daemon=True).start()
        time.sleep(1.0 / rps)


PAGE = """<!doctype html><html><head><title>NetworkView Manager</title>
<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:1.5rem auto;padding:0 1rem}
button{padding:.5rem .8rem;margin:.2rem;border:0;border-radius:6px;background:#2563eb;color:#fff;cursor:pointer}
button.alt{background:#059669}button.warn{background:#dc2626}
.card{border:1px solid #ddd;border-radius:10px;padding:1rem;margin:1rem 0}
pre{background:#0b1021;color:#7fdbff;padding:1rem;border-radius:8px;overflow:auto}
label{display:inline-block;min-width:150px}</style></head><body>
<h1>NetworkView — Control Plane</h1>

<div class="card"><h3>Backend version (blue/green)</h3>
<button onclick="setver('v1')">Activate v1</button>
<button class="alt" onclick="setver('v2')">Activate v2 (adds tax field)</button>
<span id="ver"></span></div>

<div class="card"><h3>Traffic generator</h3>
<button class="alt" onclick="traffic(true)">Start</button>
<button class="warn" onclick="traffic(false)">Stop</button>
<div><label>Requests/sec</label><input id="rps" type="number" value="3" min="1" max="50">
<button onclick="setrps()">set</button></div>
<p>Mix = HTTP + HTTPS(TLS1.3) + HTTPS(TLS1.2). Watch the sniffer + LB stats.</p></div>

<div class="card"><h3>Fault injection (backend)</h3>
<div><label>Latency ms</label><input id="lat" type="number" value="0"></div>
<div><label>Error rate 0..1</label><input id="err" type="number" step="0.1" value="0"></div>
<button onclick="setfault()">Apply</button></div>

<div class="card"><h3>State &amp; traffic stats</h3>
<button onclick="refresh()">refresh</button><pre id="state">...</pre></div>

<script>
const j = (u,m,b)=>fetch(u,{method:m||'GET',headers:{'Content-Type':'application/json'},
  body:b?JSON.stringify(b):undefined}).then(r=>r.json());
function setver(v){j('/api/version','POST',{version:v}).then(refresh);}
function traffic(on){j('/api/traffic','POST',{running:on}).then(refresh);}
function setrps(){j('/api/traffic','POST',{rps:+document.getElementById('rps').value}).then(refresh);}
function setfault(){j('/api/fault','POST',{backend_latency_ms:+document.getElementById('lat').value,
  backend_error_rate:+document.getElementById('err').value}).then(refresh);}
function refresh(){j('/api/state').then(d=>{
  document.getElementById('state').textContent=JSON.stringify(d,null,2);
  document.getElementById('ver').textContent=' active: '+d.state.active_backend_version;});}
refresh();setInterval(refresh,3000);
</script></body></html>"""


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.get("/api/state")
def api_state():
    return jsonify(state=control.read(), traffic_stats=_stats)


@app.post("/api/version")
def api_version():
    v = (request.get_json(force=True) or {}).get("version", "v1")
    v = v if v in ("v1", "v2") else "v1"
    control.update({"active_backend_version": v})
    log.info("version switched", extra={"event": "version_switch", "extra": {"version": v}})
    return jsonify(ok=True, active_backend_version=v)


@app.post("/api/traffic")
def api_traffic():
    body = request.get_json(force=True) or {}
    patch = {}
    if "running" in body:
        patch["running"] = bool(body["running"])
    if "rps" in body:
        patch["rps"] = int(body["rps"])
    if "mix" in body:
        patch["mix"] = list(body["mix"])
    control.update({"traffic": patch})
    log.info("traffic config", extra={"event": "traffic_cfg", "extra": patch})
    return jsonify(ok=True, traffic=control.read()["traffic"])


@app.post("/api/fault")
def api_fault():
    body = request.get_json(force=True) or {}
    patch = {
        "backend_latency_ms": int(body.get("backend_latency_ms", 0)),
        "backend_error_rate": float(body.get("backend_error_rate", 0.0)),
    }
    control.update({"fault_injection": patch})
    log.info("fault config", extra={"event": "fault_cfg", "extra": patch})
    return jsonify(ok=True, fault_injection=patch)


if __name__ == "__main__":
    threading.Thread(target=traffic_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), threaded=True)
