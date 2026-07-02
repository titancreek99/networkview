"""
portal - a single-page launcher & dashboard for the whole lab.

One page (http://localhost:9003) that:
  * links to every browser console (frontend HTTP/TLS1.3/TLS1.2, manager,
    logviewer, sniffer, both LB stats), opening each in a new tab;
  * shows a LIVE health dot per console (checked server-side, so no CORS);
  * can preview the HTTP consoles inline in an iframe;
  * has an "Open all" button and a topology diagram tying it together.

Health is probed from inside the docker network by service name, while the
clickable links are built in the browser from window.location.hostname + the
published host port, so it works on localhost or a remote host alike.
"""
import concurrent.futures
import json
import os
import sys
import time

import requests
from flask import Response, jsonify, render_template_string

sys.path.insert(0, "/app")
from common.appkit import make_app
from common.theme import BASE_CSS, LOGO_SVG, BRAND

app, log = make_app()
CA_BUNDLE = os.environ.get("CA_BUNDLE", "/certs/ca-chain.crt")

# id, title, group, host port, url scheme+path (built client-side),
# internal health URL (probed server-side), whether it can be iframed, blurb, tags, doc
CONSOLES = [
    {"id": "fe_http", "name": "Shop — HTTP", "group": "Application",
     "port": 8080, "scheme": "http", "path": "/", "iframe": True,
     "health": "http://lb-edge:80/healthz",
     "desc": "The app over plain HTTP. Everything is readable on the wire.",
     "tags": ["HTTP", "cleartext"], "doc": "docs/04-http-vs-https.md"},
    {"id": "fe_tls13", "name": "Shop — HTTPS / TLS 1.3", "group": "Application",
     "port": 8443, "scheme": "https", "path": "/", "iframe": False,
     "health": "https://lb-edge:443/healthz",
     "desc": "Same app, modern 1-RTT TLS 1.3 handshake. Trust the lab CA first.",
     "tags": ["HTTPS", "TLS 1.3"], "doc": "docs/03-tls12-vs-tls13.md"},
    {"id": "fe_tls12", "name": "Shop — HTTPS / TLS 1.2", "group": "Application",
     "port": 8444, "scheme": "https", "path": "/", "iframe": False,
     "health": "https://lb-edge:8443/healthz",
     "desc": "Same app pinned to TLS 1.2 — compare the handshake to 1.3.",
     "tags": ["HTTPS", "TLS 1.2"], "doc": "docs/03-tls12-vs-tls13.md"},

    {"id": "manager", "name": "Manager — Admin", "group": "Control Plane",
     "port": 9000, "scheme": "http", "path": "/", "iframe": True,
     "health": "http://manager:8000/healthz",
     "desc": "Switch versions, generate traffic, inject faults. Your driver's seat.",
     "tags": ["control", "traffic", "faults"], "doc": "docs/admin-guide.md"},
    {"id": "logs", "name": "Log Viewer", "group": "Control Plane",
     "port": 9001, "scheme": "http", "path": "/", "iframe": True,
     "health": "http://logviewer:8000/healthz",
     "desc": "Aggregated JSON logs for every service, live.",
     "tags": ["observability"], "doc": "docs/labs.md"},
    {"id": "sniffer", "name": "Packet Sniffer", "group": "Control Plane",
     "port": 9002, "scheme": "http", "path": "/", "iframe": True,
     "health": "http://sniffer:8000/healthz",
     "desc": "Decode captures: TCP handshake, TLS ClientHello, cleartext HTTP.",
     "tags": ["tshark", "TCP", "TLS"], "doc": "docs/02-tls-handshake.md"},

    {"id": "edge_stats", "name": "Edge LB — Stats", "group": "Load Balancers",
     "port": 8405, "scheme": "http", "path": "/", "iframe": True,
     "health": "http://lb-edge:8404/",
     "desc": "HAProxy 'LTM' at the edge: TLS termination + frontend pool.",
     "tags": ["HAProxy", "LTM"], "doc": "docs/labs.md"},
    {"id": "int_stats", "name": "Internal LB — Stats", "group": "Load Balancers",
     "port": 8404, "scheme": "http", "path": "/", "iframe": True,
     "health": "http://lb-int:8404/",
     "desc": "Internal HAProxy: middleware + backend pools, round-robin.",
     "tags": ["HAProxy", "pools"], "doc": "docs/labs.md"},
]


def _probe(c):
    url = c["health"]
    t0 = time.time()
    try:
        verify = CA_BUNDLE if url.startswith("https") and os.path.exists(CA_BUNDLE) else False
        r = requests.get(url, timeout=2.5, verify=verify)
        return c["id"], {"up": r.status_code < 500, "code": r.status_code,
                         "ms": round((time.time() - t0) * 1000)}
    except requests.RequestException as exc:
        return c["id"], {"up": False, "code": 0, "err": type(exc).__name__,
                         "ms": round((time.time() - t0) * 1000)}


@app.get("/api/status")
def api_status():
    out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for cid, st in ex.map(_probe, CONSOLES):
            out[cid] = st
    return jsonify(status=out, ts=int(time.time()))


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NetworkView — Portal</title><style>{{ css|safe }}{{ extra|safe }}</style></head>
<body>
{{ topbar|safe }}
<div class="wrap">
  <section class="hero">
    <h1>NetworkView <span class="grad">Console</span></h1>
    <p>One launcher for every browser tool in the lab. Green dots are live health
       checks. Click <b>Open</b> to launch a console in a new tab, or <b>Preview</b>
       to embed it here. New to the lab? Start with the
       <a href="#" onclick="openDoc('docs/labs.md');return false">guided labs</a>.</p>
    <div class="toolbar">
      <button class="btn primary" onclick="openAll()">⛶ Open all consoles</button>
      <button class="btn" onclick="refresh()">↻ Refresh health</button>
      <span class="badge"><span class="dot" id="agg"></span><span id="aggtxt" class="muted">checking…</span></span>
    </div>
  </section>

  <div id="groups"></div>

  <div class="section-title">Topology</div>
  <div class="panel" style="overflow-x:auto">{{ topo|safe }}</div>

  <div class="section-title">Concept deep-dives</div>
  <div class="grid" id="docs"></div>

  <p class="faint" style="margin:26px 0 40px">
    Tip: for the HTTPS shop tabs, trust the lab CA first —
    <code>docker compose exec manager cat /certs/ca-chain.crt &gt; ca-chain.crt</code>
  </p>
</div>

<!-- iframe preview overlay -->
<div id="modal" style="display:none;position:fixed;inset:0;z-index:50;background:rgba(3,6,16,.72);backdrop-filter:blur(4px)">
  <div style="max-width:1180px;margin:34px auto;height:calc(100vh - 68px);display:flex;flex-direction:column;
       background:var(--surface);border:1px solid var(--border-2);border-radius:14px;overflow:hidden;box-shadow:var(--shadow)">
    <div class="row" style="justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border)">
      <b id="mtitle"></b>
      <span class="row">
        <a class="btn ghost" id="mopen" target="_blank" rel="noopener">Open in tab ↗</a>
        <button class="btn" onclick="closeModal()">✕ Close</button>
      </span>
    </div>
    <iframe id="mframe" style="flex:1;border:0;background:#fff"></iframe>
  </div>
</div>

<script>
const CONSOLES = {{ consoles|safe }};
const DOCS = {{ docs|safe }};
const REPO = "https://github.com/titancreek99/networkview/blob/main/";

const host = () => location.hostname || "localhost";
const urlFor = c => `${c.scheme}://${host()}:${c.port}${c.path}`;
function openDoc(p){ window.open(REPO + p, "_blank", "noopener"); }

function groupHtml(name, items){
  const cards = items.map(c => `
    <div class="card">
      <h3><span class="dot" id="dot-${c.id}"></span>${c.name}</h3>
      <p class="desc">${c.desc}</p>
      <div class="tags" style="margin-bottom:12px">${c.tags.map(t=>`<span class="tag">${t}</span>`).join("")}</div>
      <div class="btn-row">
        <a class="btn primary" href="${urlFor(c)}" target="_blank" rel="noopener">Open ↗</a>
        ${c.iframe ? `<button class="btn" onclick='preview(${JSON.stringify(c)})'>Preview</button>` : ""}
        <a class="btn ghost" href="${REPO}${c.doc}" target="_blank" rel="noopener">Docs</a>
        <span class="badge" style="margin-left:auto"><span class="muted" id="lat-${c.id}"></span></span>
      </div>
    </div>`).join("");
  return `<div class="section-title">${name}</div><div class="grid">${cards}</div>`;
}

function render(){
  const groups = [...new Set(CONSOLES.map(c=>c.group))];
  document.getElementById("groups").innerHTML =
    groups.map(g => groupHtml(g, CONSOLES.filter(c=>c.group===g))).join("");
  document.getElementById("docs").innerHTML = DOCS.map(d=>`
    <div class="card">
      <h3>${d.icon} ${d.title}</h3><p class="desc">${d.desc}</p>
      <a class="btn ghost" href="${REPO}${d.path}" target="_blank" rel="noopener">Read ↗</a>
    </div>`).join("");
}

function preview(c){
  document.getElementById("mtitle").textContent = c.name;
  document.getElementById("mframe").src = urlFor(c);
  document.getElementById("mopen").href = urlFor(c);
  document.getElementById("modal").style.display = "block";
}
function closeModal(){ document.getElementById("modal").style.display="none";
  document.getElementById("mframe").src="about:blank"; }
document.addEventListener("keydown",e=>{ if(e.key==="Escape") closeModal(); });

function openAll(){
  CONSOLES.forEach((c,i)=> setTimeout(()=>window.open(urlFor(c),"_blank","noopener"), i*250));
}

function refresh(){
  fetch("/api/status").then(r=>r.json()).then(d=>{
    let up=0, tot=0;
    CONSOLES.forEach(c=>{
      tot++; const s=d.status[c.id]||{};
      const dot=document.getElementById("dot-"+c.id);
      const lat=document.getElementById("lat-"+c.id);
      if(dot){ dot.className = "dot " + (s.up ? "up":"down"); }
      if(lat){ lat.textContent = s.up ? `${s.code} · ${s.ms}ms` : (s.err||"down"); }
      if(s.up) up++;
    });
    const agg=document.getElementById("agg"), t=document.getElementById("aggtxt");
    agg.className = "dot " + (up===tot?"up":(up===0?"down":"warn"));
    t.textContent = `${up}/${tot} consoles healthy`;
  }).catch(()=>{ document.getElementById("aggtxt").textContent="health check failed"; });
}
render(); refresh(); setInterval(refresh, 5000);
</script>
</body></html>"""

# Simple, responsive CSS topology (no external assets).
TOPO = """
<style>
.topo{display:flex;align-items:stretch;gap:0;min-width:820px;font-size:12.5px}
.tier{display:flex;flex-direction:column;gap:8px;justify-content:center;padding:0 6px}
.node{background:var(--surface-2);border:1px solid var(--border-2);border-radius:10px;
  padding:9px 12px;text-align:center;min-width:118px}
.node b{display:block} .node small{color:var(--muted)}
.node.edge{border-color:#3b56c8;background:linear-gradient(180deg,#1b2660,#141c40)}
.node.lb{border-color:#7a4fd6;background:linear-gradient(180deg,#241a4d,#171233)}
.node.data{border-color:#0e7c6b;background:linear-gradient(180deg,#0f2e2b,#0c1f22)}
.arrow{display:flex;flex-direction:column;justify-content:center;color:var(--faint);padding:0 4px;white-space:nowrap}
.arrow small{color:var(--faint)}
.enc{color:var(--ok)} .plain{color:var(--warn)}
</style>
<div class="topo">
  <div class="tier"><div class="node"><b>Client</b><small>browser / curl</small></div></div>
  <div class="arrow"><div>──▶</div><small class="enc">TLS</small></div>
  <div class="tier"><div class="node edge"><b>lb-edge</b><small>TLS term · :8080/8443/8444</small></div></div>
  <div class="arrow"><div>──▶</div><small class="plain">http</small></div>
  <div class="tier">
    <div class="node"><b>frontend-1</b></div><div class="node"><b>frontend-2</b></div>
  </div>
  <div class="arrow"><div>──▶</div><small>lb-int:8081</small></div>
  <div class="tier">
    <div class="node"><b>middleware-1</b></div><div class="node"><b>middleware-2</b></div>
  </div>
  <div class="arrow"><div>──▶</div><small>lb-int:8082</small></div>
  <div class="tier">
    <div class="node"><b>backend-1</b></div><div class="node"><b>backend-2</b></div>
  </div>
  <div class="arrow"><div>──▶</div><small>psql</small></div>
  <div class="tier"><div class="node data"><b>postgres</b><small>orders</small></div></div>
</div>
"""

DOCS = [
    {"icon": "🔗", "title": "TCP handshake", "path": "docs/01-tcp-handshake.md",
     "desc": "SYN / SYN-ACK / ACK and why it precedes everything."},
    {"icon": "🔐", "title": "TLS handshake", "path": "docs/02-tls-handshake.md",
     "desc": "ClientHello, ServerHello, key agreement, forward secrecy."},
    {"icon": "⚖️", "title": "TLS 1.2 vs 1.3", "path": "docs/03-tls12-vs-tls13.md",
     "desc": "Round-trips, cipher suites, encrypted certificate."},
    {"icon": "📨", "title": "HTTP vs HTTPS", "path": "docs/04-http-vs-https.md",
     "desc": "Cleartext vs encrypted, and the plaintext internal hops."},
    {"icon": "📜", "title": "Certificate signing", "path": "docs/05-certificate-signing.md",
     "desc": "Root → Intermediate → leaf chain of trust."},
    {"icon": "🕵️", "title": "Man-in-the-Middle", "path": "docs/06-mitm.md",
     "desc": "Why validation defeats interception (and -k doesn't)."},
    {"icon": "🎛️", "title": "Admin guide", "path": "docs/admin-guide.md",
     "desc": "Drive every concept from the Manager console."},
    {"icon": "🧪", "title": "Guided labs", "path": "docs/labs.md",
     "desc": "Step-by-step exercises for each topic."},
]

EXTRA_CSS = """
.navlink.active{color:var(--text);background:var(--surface)}
"""


@app.get("/")
def index():
    from common.theme import topbar
    return render_template_string(
        PAGE, css=BASE_CSS, extra=EXTRA_CSS, topbar=topbar("portal"),
        topo=TOPO, consoles=json.dumps(CONSOLES), docs=json.dumps(DOCS))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), threaded=True)
