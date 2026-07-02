"""
middleware - tier 2. The "connecting middleware" / BFF.

Receives requests from the frontend, enriches them, and calls the backend
*through the internal load balancer* (lb-int). It does not touch the DB.
This is the hop where you can watch INTERNAL, PLAINTEXT HTTP traffic in the
packet sniffer - a deliberate contrast with the TLS-terminated edge.
"""
import os
import sys

import requests
from flask import jsonify

sys.path.insert(0, "/app")
from common.appkit import make_app, HOSTNAME, APP_VERSION

app, log = make_app()

# middleware -> internal LB -> backend pool (plaintext HTTP on purpose)
BACKEND_URL = os.environ.get("BACKEND_URL", "http://lb-int:8082")


@app.get("/mw/orders")
def orders():
    try:
        resp = requests.get(f"{BACKEND_URL}/api/orders", timeout=5)
        log.info("called backend", extra={"event": "upstream_call",
                 "upstream": BACKEND_URL, "status": resp.status_code})
        payload = resp.json()
    except requests.RequestException as exc:
        log.error("backend call failed", extra={"event": "upstream_error",
                  "upstream": BACKEND_URL, "extra": {"err": str(exc)[:160]}})
        return jsonify(error="backend unreachable", detail=str(exc)[:160]), 502

    return jsonify(
        middleware={"host": HOSTNAME, "version": APP_VERSION},
        note="middleware->backend hop is plaintext HTTP; sniff it!",
        backend=payload,
    ), resp.status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), threaded=True)
