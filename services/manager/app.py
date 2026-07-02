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
from common.theme import BASE_CSS, topbar

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


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NetworkView — Manager</title><style>{{ css|safe }}
.kpi{display:flex;gap:10px;flex-wrap:wrap}
.kpi .box{flex:1;min-width:120px;background:var(--bg-2);border:1px solid var(--border);
  border-radius:10px;padding:12px 14px}
.kpi .n{font-size:22px;font-weight:700} .kpi .l{color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.08em}
.ver-pill{font-size:12px;padding:3px 10px;border-radius:999px;border:1px solid var(--border-2);background:var(--surface-2)}
</style></head><body>
{{ topbar|safe }}
<div class="wrap">
  <section class="hero">
    <h1>Control <span class="grad">Plane</span></h1>
    <p>Drive every experiment from here. Each control produces a visible effect in
       the sniffer, logs, or LB stats — see the
       <a href="https://github.com/titancreek99/networkview/blob/main/docs/admin-guide.md" target="_blank" rel="noopener">admin guide</a>.</p>
  </section>

  <div class="grid">
    <div class="panel">
      <h3>Backend version <span class="ver-pill" id="ver">—</span></h3>
      <p class="muted">Blue/green switch, applied fleet-wide on the next request.</p>
      <div class="btn-row">
        <button class="btn primary" onclick="setver('v1')">Activate v1</button>
        <button class="btn ok" onclick="setver('v2')">Activate v2 · +tax field</button>
      </div>
    </div>

    <div class="panel">
      <h3>Traffic generator</h3>
      <p class="muted">Mixes HTTP + HTTPS(TLS 1.3) + HTTPS(TLS 1.2) through the edge LB.</p>
      <div class="btn-row" style="margin-bottom:10px">
        <button class="btn ok" onclick="traffic(true)">▶ Start</button>
        <button class="btn err" onclick="traffic(false)">■ Stop</button>
      </div>
      <div class="row">
        <label>Requests/sec</label>
        <input id="rps" type="number" value="3" min="1" max="50" style="width:90px">
        <button class="btn" onclick="setrps()">Set</button>
      </div>
    </div>

    <div class="panel">
      <h3>Fault injection <span class="tag">backend</span></h3>
      <p class="muted">Watch latency/errors ripple up through the tiers.</p>
      <div class="row" style="margin-bottom:8px">
        <label style="min-width:110px">Latency ms</label>
        <input id="lat" type="number" value="0" style="width:110px">
      </div>
      <div class="row" style="margin-bottom:12px">
        <label style="min-width:110px">Error rate 0–1</label>
        <input id="err" type="number" step="0.1" value="0" style="width:110px">
      </div>
      <button class="btn warn" onclick="setfault()">Apply</button>
    </div>
  </div>

  <div class="section-title">Live state &amp; traffic</div>
  <div class="panel">
    <div class="kpi" id="kpi" style="margin-bottom:14px"></div>
    <div class="row" style="margin-bottom:10px">
      <button class="btn" onclick="refresh()">↻ Refresh</button>
      <span class="badge muted" id="tstate"></span>
    </div>
    <pre id="state">…</pre>
  </div>
  <div style="height:40px"></div>
</div>

<script>
const j = (u,m,b)=>fetch(u,{method:m||'GET',headers:{'Content-Type':'application/json'},
  body:b?JSON.stringify(b):undefined}).then(r=>r.json());
function setver(v){j('/api/version','POST',{version:v}).then(refresh);}
function traffic(on){j('/api/traffic','POST',{running:on}).then(refresh);}
function setrps(){j('/api/traffic','POST',{rps:+document.getElementById('rps').value}).then(refresh);}
function setfault(){j('/api/fault','POST',{backend_latency_ms:+document.getElementById('lat').value,
  backend_error_rate:+document.getElementById('err').value}).then(refresh);}
function box(n,l){return `<div class="box"><div class="n">${n}</div><div class="l">${l}</div></div>`;}
function refresh(){j('/api/state').then(d=>{
  document.getElementById('state').textContent=JSON.stringify(d,null,2);
  document.getElementById('ver').textContent=d.state.active_backend_version;
  const s=d.traffic_stats||{}, bp=s.by_proto||{};
  document.getElementById('kpi').innerHTML =
    box(s.sent||0,'sent')+box(s.ok||0,'ok')+box(s.err||0,'err')+
    box(bp.http||0,'HTTP')+box(bp.https13||0,'TLS 1.3')+box(bp.https12||0,'TLS 1.2');
  const t=d.state.traffic||{};
  document.getElementById('tstate').textContent =
    (t.running?('● generating at '+t.rps+' rps'):'○ traffic stopped');
});}
refresh();setInterval(refresh,3000);
</script></body></html>"""


@app.get("/")
def index():
    return render_template_string(PAGE, css=BASE_CSS, topbar=topbar("manager"))


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
