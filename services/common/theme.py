"""
theme.py - one shared design system for every NetworkView console.

Exposes BASE_CSS (a dark, modern, accessible style sheet built on CSS custom
properties) plus small helpers so each Flask app renders with a consistent look
without copy-pasting styles. Colors are chosen for AA contrast on the dark
surface and to read the same across all consoles.
"""

BRAND = {
    "name": "NetworkView",
    "tagline": "TLS · TCP · PKI · MITM · Load Balancing — hands-on",
}

# A single stylesheet shared by portal, manager, logviewer, sniffer, frontend.
BASE_CSS = """
:root{
  --bg:#0b1020; --bg-2:#111830; --surface:#151d38; --surface-2:#1b2547;
  --border:#26304f; --border-2:#334066;
  --text:#e7ecff; --muted:#9aa6cc; --faint:#6b779c;
  --brand:#6d8bff; --brand-2:#8b5cff; --accent:#22d3ee;
  --ok:#34d399; --warn:#fbbf24; --err:#f87171; --info:#60a5fa;
  --radius:14px; --radius-sm:9px; --shadow:0 10px 30px rgba(0,0,0,.35);
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
}
*{box-sizing:border-box}
html{color-scheme:dark}
body{
  margin:0; font-family:var(--sans); color:var(--text);
  background:
    radial-gradient(1200px 600px at 15% -10%, rgba(109,139,255,.16), transparent 60%),
    radial-gradient(1000px 500px at 110% 0%, rgba(139,92,255,.14), transparent 55%),
    var(--bg);
  min-height:100vh; line-height:1.5;
}
a{color:var(--brand); text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1200px; margin:0 auto; padding:0 20px}

/* Top bar */
.topbar{position:sticky; top:0; z-index:20; backdrop-filter:blur(10px);
  background:linear-gradient(180deg, rgba(11,16,32,.92), rgba(11,16,32,.72));
  border-bottom:1px solid var(--border)}
.topbar .wrap{display:flex; align-items:center; gap:14px; height:62px}
.logo{display:flex; align-items:center; gap:11px; font-weight:700; letter-spacing:.2px}
.logo .mark{width:30px; height:30px; border-radius:9px;
  background:linear-gradient(135deg,var(--brand),var(--brand-2));
  box-shadow:0 4px 14px rgba(109,139,255,.5); display:grid; place-items:center}
.logo .mark svg{width:18px; height:18px}
.logo small{display:block; font-weight:500; color:var(--muted); font-size:11px; letter-spacing:.3px}
.spacer{flex:1}
.navlink{color:var(--muted); font-size:14px; padding:7px 12px; border-radius:8px}
.navlink:hover{color:var(--text); background:var(--surface); text-decoration:none}

/* Hero */
.hero{padding:34px 0 10px}
.hero h1{margin:0 0 8px; font-size:30px; letter-spacing:-.02em}
.hero p{margin:0; color:var(--muted); max-width:70ch}
.grad{background:linear-gradient(90deg,var(--brand),var(--accent) 60%,var(--brand-2));
  -webkit-background-clip:text; background-clip:text; color:transparent}

/* Cards & grid */
.grid{display:grid; gap:16px; grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}
.card{background:linear-gradient(180deg,var(--surface),var(--bg-2));
  border:1px solid var(--border); border-radius:var(--radius); padding:18px;
  box-shadow:var(--shadow); transition:transform .12s ease, border-color .12s ease}
.card:hover{transform:translateY(-2px); border-color:var(--border-2)}
.card h3{margin:0 0 6px; font-size:16px; display:flex; align-items:center; gap:9px}
.card .desc{color:var(--muted); font-size:13.5px; margin:0 0 12px}
.section-title{font-size:12px; text-transform:uppercase; letter-spacing:.14em;
  color:var(--faint); margin:26px 0 12px; font-weight:700}

/* Buttons */
.btn{display:inline-flex; align-items:center; gap:7px; cursor:pointer;
  font:inherit; font-size:13.5px; font-weight:600; color:var(--text);
  background:var(--surface-2); border:1px solid var(--border-2);
  padding:8px 13px; border-radius:var(--radius-sm); transition:.12s}
.btn:hover{border-color:var(--brand); text-decoration:none}
.btn.primary{background:linear-gradient(135deg,var(--brand),var(--brand-2));
  border-color:transparent; box-shadow:0 6px 18px rgba(109,139,255,.35)}
.btn.ok{background:linear-gradient(135deg,#0f9d6b,#34d399); border-color:transparent; color:#04211a}
.btn.warn{background:linear-gradient(135deg,#b45309,#fbbf24); border-color:transparent; color:#241503}
.btn.err{background:linear-gradient(135deg,#b91c1c,#f87171); border-color:transparent; color:#2a0606}
.btn.ghost{background:transparent}
.btn:disabled{opacity:.5; cursor:not-allowed}
.btn-row{display:flex; flex-wrap:wrap; gap:8px}

/* Inputs */
input,select{font:inherit; color:var(--text); background:var(--bg-2);
  border:1px solid var(--border-2); border-radius:8px; padding:8px 10px}
input:focus,select:focus{outline:2px solid var(--brand); outline-offset:1px}
label{color:var(--muted); font-size:13px}

/* Pills / tags / status */
.tag{font-size:11px; font-weight:600; color:var(--muted); background:var(--surface-2);
  border:1px solid var(--border); border-radius:999px; padding:2px 9px}
.tags{display:flex; flex-wrap:wrap; gap:6px}
.dot{width:9px; height:9px; border-radius:50%; background:var(--faint);
  box-shadow:0 0 0 3px rgba(255,255,255,.03); flex:0 0 auto}
.dot.up{background:var(--ok); box-shadow:0 0 0 3px rgba(52,211,153,.18)}
.dot.down{background:var(--err); box-shadow:0 0 0 3px rgba(248,113,113,.18)}
.dot.warn{background:var(--warn)}
.badge{display:inline-flex; align-items:center; gap:7px; font-size:12px; color:var(--muted)}

/* Tables */
table{width:100%; border-collapse:collapse; font-size:13px}
th,td{text-align:left; padding:7px 10px; border-bottom:1px solid var(--border)}
th{color:var(--faint); font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:.08em}
tbody tr:hover{background:var(--surface)}

/* Code / pre */
pre{background:#070b18; border:1px solid var(--border); color:#a9d3ff;
  padding:14px; border-radius:var(--radius-sm); overflow:auto; font-family:var(--mono);
  font-size:12.5px; line-height:1.5}
code{font-family:var(--mono); background:var(--surface-2); border:1px solid var(--border);
  padding:1px 6px; border-radius:6px; font-size:12.5px}

/* Panels */
.panel{background:linear-gradient(180deg,var(--surface),var(--bg-2));
  border:1px solid var(--border); border-radius:var(--radius); padding:18px; box-shadow:var(--shadow)}
.row{display:flex; gap:12px; align-items:center; flex-wrap:wrap}
.muted{color:var(--muted)} .faint{color:var(--faint)}
.toolbar{display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin:6px 0 16px}
hr{border:0; border-top:1px solid var(--border); margin:18px 0}
::-webkit-scrollbar{height:10px; width:10px}
::-webkit-scrollbar-thumb{background:var(--border-2); border-radius:10px}
"""

# Small inline SVG logo mark reused across consoles.
LOGO_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="3"/><circle cx="4" cy="5" r="2"/>'
    '<circle cx="20" cy="5" r="2"/><circle cx="4" cy="19" r="2"/>'
    '<circle cx="20" cy="19" r="2"/><path d="M6 6l4 4M18 6l-4 4M6 18l4-4M18 18l-4-4"/></svg>'
)


def topbar(active: str = "") -> str:
    """Shared sticky header with logo + links back to the portal and consoles."""
    def link(href, label, key):
        cls = "navlink" + (" active" if key == active else "")
        return f'<a class="{cls}" href="{href}" target="_blank" rel="noopener">{label}</a>'
    return f"""
<div class="topbar"><div class="wrap">
  <a class="logo" href="/" style="color:var(--text)">
    <span class="mark">{LOGO_SVG}</span>
    <span>{BRAND['name']}<small>{BRAND['tagline']}</small></span>
  </a>
  <span class="spacer"></span>
  {link('http://localhost:9003/', 'Portal', 'portal')}
  {link('http://localhost:9000/', 'Manager', 'manager')}
  {link('http://localhost:9001/', 'Logs', 'logs')}
  {link('http://localhost:9002/', 'Sniffer', 'sniffer')}
</div></div>
"""
