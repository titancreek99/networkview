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

app, log = make_app()

MIDDLEWARE_URL = os.environ.get("MIDDLEWARE_URL", "http://lb-int:8081")

PAGE = """<!doctype html><html><head><title>NetworkView Shop</title>
<style>body{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem}
pre{background:#0b1021;color:#7fdbff;padding:1rem;border-radius:8px;overflow:auto}
h1{color:#111}.pill{background:#eef;padding:2px 8px;border-radius:10px;font-size:.8rem}</style>
</head><body>
<h1>NetworkView Shop <span class="pill">served by {{host}} ({{ver}})</span></h1>
<p>This is the <b>frontend</b>. It calls the <b>middleware</b>, which calls the
<b>backend</b> (via internal LB), which reads <b>Postgres</b>.</p>
<p><a href="/orders">/orders (fetch through the whole stack)</a></p>
<h3>Live data</h3><pre id="out">loading...</pre>
<script>
fetch('/orders').then(r=>r.json()).then(d=>{
  document.getElementById('out').textContent = JSON.stringify(d,null,2);
}).catch(e=>{document.getElementById('out').textContent='error: '+e;});
</script>
</body></html>"""


@app.get("/")
def index():
    return render_template_string(PAGE, host=HOSTNAME, ver=APP_VERSION)


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
