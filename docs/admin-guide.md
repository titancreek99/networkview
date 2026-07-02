# Admin app (Manager) — deep-dive driver's guide

The **Manager** at `http://localhost:9000` is the control plane you drive every
experiment from. It doesn't just start/stop things — each control is a lever
designed to *produce an observable effect* in one of the other consoles:

```
        ┌────────────── Manager (:9000) ───────────────┐
        │  version switch │ traffic gen │ fault inject  │
        └───────┬─────────────────┬───────────────┬─────┘
                │ writes           │ generates     │ writes
                ▼                  ▼               ▼
        control store        real requests    control store
                │            through edge LB        │
   backend reads│                  │          backend reads
                ▼                  ▼               ▼
        Frontend (:8080)   Sniffer (:9002)   Backend logs (:9001)
        shows v1/v2        TCP/TLS/HTTP       latency / 503s
                           LB stats (:8404/5) spread load
```

Keep these four tabs open while you work: **Manager (:9000)**,
**Sniffer (:9002)**, **Log viewer (:9001)**, and **LB stats (:8405 edge /
:8404 internal)**.

---

## 1. The three control panels

### A. Backend version (blue/green)
| Button | Effect |
|---|---|
| **Activate v1** | backend returns plain orders |
| **Activate v2** | backend adds an `amount_with_tax` field to every order |

The choice is written to the shared control store; **all** backend replicas read
it on the next request — so a switch is instant and fleet-wide, with no
redeploy. This models a blue/green / feature-flag version cutover.

### B. Traffic generator
| Control | Effect |
|---|---|
| **Start / Stop** | turn the background request loop on/off |
| **Requests/sec** | how many requests/sec to fire (1–50) |

The generator sends each request through the **edge LB**, randomly choosing
among **HTTP (:80)**, **HTTPS/TLS 1.3 (:443)** and **HTTPS/TLS 1.2 (:8443)** —
so a single "Start" click gives the sniffer all three transports to compare and
gives both LBs load to distribute.

### C. Fault injection (backend)
| Field | Effect |
|---|---|
| **Latency ms** | backend sleeps this long before responding |
| **Error rate 0..1** | fraction of backend requests that return HTTP 503 |

Both are honored by every backend replica on the next request, so you can watch
latency/error propagate up through middleware → frontend and show up in the LB
stats and logs.

### D. State & traffic stats
The **refresh** panel shows the live control-store state plus the generator's
counters (`sent`, `ok`, `err`, and a `by_proto` breakdown of HTTP vs TLS1.2 vs
TLS1.3). Use it to confirm a setting actually took effect.

---

## 2. Driving each concept from the Manager

### TCP + TLS handshakes
1. Manager → **Start** traffic (rps 3 is plenty).
2. Sniffer → `edge` capture → **TCP handshake** to see SYN/SYN-ACK/ACK, then
   **TLS ClientHello / ServerHello** to see negotiation.
3. Stop traffic when done so captures stop growing.

*Tip:* lower rps to **1** to get clean, well-separated connections that are easy
to read packet-by-packet; raise it to **20+** to stress the LB.

### TLS 1.2 vs 1.3
The generator already mixes both. To isolate one:
- Watch the **by_proto** counter in the state panel to confirm both fire.
- In the `edge` capture, filter **TLS handshake** and compare a `:8443` (1.3)
  flow against a `:8444`-style (1.2) flow — the 1.2 one shows a readable
  `Certificate` record; the 1.3 one doesn't.

### HTTP vs HTTPS (and "internal is not trusted")
1. Start traffic. Sniffer → `edge` → **HTTP (cleartext)**: only the `:80`
   requests are readable; the TLS ports are opaque.
2. Sniffer → `internal` → **HTTP (cleartext)**: read the frontend→middleware→
   backend hops *in full*, even though users came in over HTTPS. This is the
   payoff — the Manager generated HTTPS traffic, yet the internal legs are
   cleartext.

### Load balancing (LTM)
1. Start traffic at **rps 10**.
2. Open **edge stats (:8405)** and **internal stats (:8404)** — watch sessions
   spread round-robin across the `frontend_pool` / `middleware_pool` /
   `backend_pool` servers.
3. Scale up: `docker compose up -d --scale backend=4`, then watch the internal
   stats show 4 healthy `backend` servers now sharing the load.

### Version management (blue/green)
1. With traffic running, click **Activate v2**.
2. Refresh the Frontend (`:8080`) or watch the `backend` logs (`:9001`) — the
   `active_version` flips to `v2` and responses gain `amount_with_tax`, with no
   restart. Flip back to **v1** and confirm it reverts.

### Fault injection → resilience
1. Set **Latency ms = 800**, Apply. Watch `duration_ms` climb in the `backend`
   and `middleware` logs, and response times rise in the LB stats.
2. Set **Error rate = 0.3**, Apply. Watch 503s appear in `backend` logs
   (`event: fault`) and the edge LB stats error counters tick up; the frontend
   surfaces `502/503`. Reset both to 0 to recover.

---

## 3. Same controls via the HTTP API

Every button is a thin wrapper over a JSON API — handy for scripting labs or
correlating an exact timestamp with a capture.

```bash
M=http://localhost:9000

# Inspect current state + traffic counters
curl -s $M/api/state | python3 -m json.tool

# Blue/green version switch
curl -s -XPOST $M/api/version -H 'content-type: application/json' -d '{"version":"v2"}'

# Traffic generator: start at 10 rps, HTTPS-only mix, then stop
curl -s -XPOST $M/api/traffic -H 'content-type: application/json' \
     -d '{"running":true,"rps":10,"mix":["https13","https12"]}'
curl -s -XPOST $M/api/traffic -H 'content-type: application/json' -d '{"running":false}'

# Fault injection: 800ms latency + 30% errors, then clear
curl -s -XPOST $M/api/fault -H 'content-type: application/json' \
     -d '{"backend_latency_ms":800,"backend_error_rate":0.3}'
curl -s -XPOST $M/api/fault -H 'content-type: application/json' \
     -d '{"backend_latency_ms":0,"backend_error_rate":0}'
```

`mix` accepts any of `http`, `https13`, `https12` — restrict it to force the
generator to exercise exactly the transport you're studying.

---

## 4. A 10-minute guided session

1. **Start** traffic at rps 3. Confirm `by_proto` shows all three transports.
2. Sniffer `edge`: walk a TCP handshake, then a TLS ClientHello/ServerHello.
3. Sniffer `edge` → HTTP view: read a `:80` request. Note `:443/:8443` are opaque.
4. Sniffer `internal` → HTTP view: read the plaintext internal hops. Discuss
   zero-trust.
5. Manager: **Activate v2** → confirm the tax field in the Frontend + logs.
6. Manager: **rps 15**, open both LB stats, watch load spread; `--scale backend=4`.
7. Manager: **latency 800ms**, then **error 0.3** → watch logs + LB react, then reset.
8. `docker compose --profile mitm up -d mitm` → run the two curl commands from
   [`06-mitm.md`](06-mitm.md) to see validation defeat/permit the attack.

You've now driven every concept in the lab from a single console. See
[`labs.md`](labs.md) for the standalone exercises.
