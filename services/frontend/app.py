"""
frontend - tier 1. The user-facing web app.

Renders a small dashboard and proxies "get orders" to the middleware. Sits
behind lb-edge which terminates TLS, so the browser<->edge leg is HTTPS while
frontend<->middleware is plaintext HTTP.
"""
import os
import sys

import requests
from flask import jsonify, render_template_string

sys.path.insert(0, "/app")
from common.appkit import make_app, HOSTNAME, APP_VERSION
from common.theme import BASE_CSS, topbar

app, log = make_app()

MIDDLEWARE_URL = os.environ.get("MIDDLEWARE_URL", "http://lb-int:8081")

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NetworkView — Shop</title><style>{{ css|safe }}
.path{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:6px 0 18px;font-size:13px}
.path .hop{background:var(--surface-2);border:1px solid var(--border-2);border-radius:8px;padding:5px 11px}
.path .sep{color:var(--faint)}
</style></head><body>
{{ topbar|safe }}
<div class="wrap">
  <section class="hero">
    <h1>NetworkView <span class="grad">Shop</span></h1>
    <p>You're looking at the <b>frontend</b> tier
       <span class="tag">served by {{host}} · {{ver}}</span>. Reload to watch the
       edge load balancer round-robin you across replicas.</p>
    <div class="path">
      <span class="hop">browser</span><span class="sep">──TLS──▶</span>
      <span class="hop">lb-edge</span><span class="sep">─▶</span>
      <span class="hop">frontend</span><span class="sep">─http─▶</span>
      <span class="hop">middleware</span><span class="sep">─▶</span>
      <span class="hop">backend</span><span class="sep">─▶</span>
      <span class="hop">postgres</span>
    </div>
  </section>

  <div class="panel">
    <div class="row" style="justify-content:space-between;margin-bottom:10px">
      <h3 style="margin:0">Live data — full stack round trip</h3>
      <button class="btn primary" onclick="load()">↻ Fetch /orders</button>
    </div>
    <pre id="out">loading…</pre>
  </div>
  <div style="height:40px"></div>
</div>
<script>
function load(){
  document.getElementById('out').textContent='loading…';
  fetch('/orders').then(r=>r.json()).then(d=>{
    document.getElementById('out').textContent = JSON.stringify(d,null,2);
  }).catch(e=>{document.getElementById('out').textContent='error: '+e;});
}
load();
</script>
</body></html>"""


@app.get("/")
def index():
    return render_template_string(PAGE, css=BASE_CSS, topbar=topbar(""),
                                  host=HOSTNAME, ver=APP_VERSION)


@app.get("/orders")
def orders():
    try:
        resp = requests.get(f"{MIDDLEWARE_URL}/mw/orders", timeout=6)
        log.info("called middleware", extra={"event": "upstream_call",
                 "upstream": MIDDLEWARE_URL, "status": resp.status_code})
        return jsonify(frontend={"host": HOSTNAME, "version": APP_VERSION},
                       downstream=resp.json()), resp.status_code
    except requests.RequestException as exc:
        log.error("middleware call failed", extra={"event": "upstream_error",
                  "upstream": MIDDLEWARE_URL, "extra": {"err": str(exc)[:160]}})
        return jsonify(error="middleware unreachable", detail=str(exc)[:160]), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), threaded=True)
