"""
sniffer - packet analysis console (read-only tshark front-end).

tcpdump sidecars capture traffic on the choke points (edge LB, internal LB,
db) into the shared /pcaps volume. This app decodes those captures with tshark
and exposes purpose-built views for the concepts we're studying:

  * TCP handshake   -> SYN / SYN-ACK / ACK
  * TLS handshake   -> ClientHello / ServerHello / Certificate
  * ClientHello deep-dive -> offered TLS versions + cipher suites (1.2 vs 1.3)
  * HTTP (plaintext) -> full cleartext requests on the internal hops
"""
import glob
import os
import subprocess
import sys

from flask import jsonify, render_template_string, request

sys.path.insert(0, "/app")
from common.appkit import make_app

app, log = make_app()
PCAP_DIR = os.environ.get("PCAP_DIR", "/pcaps")

# Named display-filter presets mapped to Wireshark/tshark filter expressions.
PRESETS = {
    "all":            "",
    "tcp_handshake":  "tcp.flags.syn==1",
    "tls_handshake":  "tls.handshake",
    "tls_clienthello": "tls.handshake.type==1",
    "tls_serverhello": "tls.handshake.type==2",
    "http":           "http",
    "dns":            "dns",
    "postgres":       "pgsql",
}

FIELDS = ["frame.number", "frame.time_relative", "ip.src", "ip.dst",
          "_ws.col.Protocol", "tcp.srcport", "tcp.dstport",
          "tcp.flags.str", "_ws.col.Info"]


def _safe_pcap(name: str) -> str | None:
    if not name or "/" in name or ".." in name:
        return None
    path = os.path.join(PCAP_DIR, name)
    return path if os.path.isfile(path) else None


def list_pcaps():
    files = []
    for p in sorted(glob.glob(os.path.join(PCAP_DIR, "*.pcap")), key=os.path.getmtime,
                    reverse=True):
        st = os.stat(p)
        files.append({"name": os.path.basename(p), "size": st.st_size,
                      "mtime": int(st.st_mtime)})
    return files


def tshark_rows(path, preset, limit):
    disp = PRESETS.get(preset, "")
    cmd = ["tshark", "-r", path, "-n"]
    if disp:
        cmd += ["-Y", disp]
    cmd += ["-T", "fields", "-E", "separator=\t"]
    for f in FIELDS:
        cmd += ["-e", f]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return [], "tshark timed out"
    rows = []
    for line in out.stdout.splitlines()[:limit]:
        cols = line.split("\t")
        cols += [""] * (len(FIELDS) - len(cols))
        rows.append(dict(zip(
            ["no", "time", "src", "dst", "proto", "sport", "dport", "flags", "info"],
            cols)))
    return rows, out.stderr.strip()


def tshark_detail(path, frame_no):
    cmd = ["tshark", "-r", path, "-n", "-Y", f"frame.number=={int(frame_no)}", "-V"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return out.stdout or out.stderr
    except (subprocess.TimeoutExpired, ValueError) as exc:
        return f"error: {exc}"


PAGE = """<!doctype html><html><head><title>NetworkView Sniffer</title>
<style>body{font-family:system-ui,sans-serif;max-width:1200px;margin:1rem auto;padding:0 1rem}
select,button{padding:.4rem;margin:.2rem}
table{width:100%;border-collapse:collapse;font-size:.82rem}
td,th{border-bottom:1px solid #eee;padding:3px 6px;text-align:left}
tr:hover{background:#eef;cursor:pointer}
pre{background:#0b1021;color:#9cdcfe;padding:1rem;border-radius:8px;max-height:460px;overflow:auto;font-size:.78rem}
.tag{font-size:.7rem;background:#eef;border-radius:8px;padding:1px 6px}</style></head><body>
<h1>NetworkView — Packet Sniffer</h1>
<div>Capture: <select id="pcap"></select>
View: <select id="preset">
<option value="all">all</option>
<option value="tcp_handshake">TCP handshake (SYN/ACK)</option>
<option value="tls_handshake">TLS handshake</option>
<option value="tls_clienthello">TLS ClientHello</option>
<option value="tls_serverhello">TLS ServerHello</option>
<option value="http">HTTP (cleartext)</option>
<option value="postgres">Postgres</option>
<option value="dns">DNS</option></select>
<button onclick="load()">decode</button>
<span class="tag">click a row for full dissection (cipher suites, versions, cert)</span></div>
<table><thead><tr><th>#</th><th>t</th><th>src</th><th>dst</th><th>proto</th>
<th>ports</th><th>flags</th><th>info</th></tr></thead><tbody id="rows"></tbody></table>
<h3>Packet detail</h3><pre id="detail">select a packet…</pre>
<script>
let cur='';
function pcaps(){return fetch('/api/captures').then(r=>r.json()).then(d=>{
  const s=document.getElementById('pcap');const c=s.value;
  s.innerHTML=d.map(f=>`<option value="${f.name}">${f.name} (${(f.size/1024).toFixed(0)}KB)</option>`).join('');
  if(c)s.value=c;});}
function load(){
  cur=document.getElementById('pcap').value;
  const p=new URLSearchParams({file:cur,preset:document.getElementById('preset').value,limit:400});
  fetch('/api/decode?'+p).then(r=>r.json()).then(d=>{
    document.getElementById('rows').innerHTML=(d.rows||[]).map(r=>
      `<tr onclick="detail(${r.no})"><td>${r.no}</td><td>${(+r.time).toFixed(3)}</td>
       <td>${r.src}</td><td>${r.dst}</td><td>${r.proto}</td>
       <td>${r.sport}&rarr;${r.dport}</td><td>${r.flags}</td><td>${r.info}</td></tr>`).join('');
    if(d.stderr)document.getElementById('detail').textContent=d.stderr;});}
function detail(n){fetch('/api/detail?'+new URLSearchParams({file:cur,frame:n}))
  .then(r=>r.json()).then(d=>{document.getElementById('detail').textContent=d.detail;});}
pcaps();setInterval(pcaps,4000);
</script></body></html>"""


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.get("/api/captures")
def api_captures():
    return jsonify(list_pcaps())


@app.get("/api/decode")
def api_decode():
    path = _safe_pcap(request.args.get("file", ""))
    if not path:
        return jsonify(rows=[], stderr="no such capture")
    rows, err = tshark_rows(path, request.args.get("preset", "all"),
                            int(request.args.get("limit", 400)))
    return jsonify(rows=rows, stderr=err)


@app.get("/api/detail")
def api_detail():
    path = _safe_pcap(request.args.get("file", ""))
    if not path:
        return jsonify(detail="no such capture")
    return jsonify(detail=tshark_detail(path, request.args.get("frame", "1")))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), threaded=True)
