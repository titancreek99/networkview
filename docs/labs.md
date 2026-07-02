# Guided labs

Bring the stack up first:

```bash
docker compose up -d --build
docker compose exec manager cat /certs/ca-chain.crt > ca-chain.crt   # local trust anchor
```

Consoles: Frontend `:8080`/`:8443`/`:8444` · Manager `:9000` · Logs `:9001` ·
Sniffer `:9002` · Edge LB stats `:8405` · Internal LB stats `:8404`.

---

## Lab 0 — Warm up the stack
1. Open the **Manager** (`:9000`) and click **Start** (traffic ~3 rps).
2. Open the **Frontend** (`http://localhost:8080`) — see live orders.
3. Open the **Log viewer** (`:9001`), select `frontend`, then `middleware`,
   then `backend`: watch one request light up all three tiers.
4. Open both LB stats pages and watch requests spread across the replica pools.

## Lab 1 — TCP handshake (→ [`01-tcp-handshake.md`](01-tcp-handshake.md))
1. Sniffer → `edge` capture → **TCP handshake (SYN/ACK)**.
2. Identify the `S`, `S.`, `.` sequence. Click the SYN → read ISN, MSS, window.
3. Bonus: find the FIN/RST that tears a connection down.

## Lab 2 — TLS handshake (→ [`02-tls-handshake.md`](02-tls-handshake.md))
1. Sniffer → `edge` → **TLS ClientHello**. Click it → read offered versions,
   cipher list, and the **SNI** hostname (cleartext!).
2. Switch to **TLS ServerHello** → note the *single* chosen cipher suite.
3. CLI: `openssl s_client -connect localhost:8443 -CAfile ca-chain.crt -servername lb-edge`

## Lab 3 — TLS 1.2 vs 1.3 (→ [`03-tls12-vs-tls13.md`](03-tls12-vs-tls13.md))
1. `openssl s_client -connect localhost:8444 -tls1_2 ...` vs `:8443 -tls1_3`.
2. In the `edge` capture compare handshakes: find the **visible Certificate** on
   1.2 (`:8444`) that is **absent/encrypted** on 1.3 (`:8443`).
3. Prove version pinning: `openssl s_client -connect localhost:8443 -tls1_2` fails.

## Lab 4 — HTTP vs HTTPS (→ [`04-http-vs-https.md`](04-http-vs-https.md))
1. Sniffer → `edge` → **HTTP (cleartext)**: read the `:8080` requests/bodies.
2. Confirm the `:8443` traffic is unreadable (encrypted `Application Data`).
3. Sniffer → `internal` → **HTTP (cleartext)**: read the frontend→middleware→
   backend hops in full — cleartext *behind* the HTTPS edge.

## Lab 5 — Certificate signing (→ [`05-certificate-signing.md`](05-certificate-signing.md))
1. `openssl verify -CAfile ca-chain.crt edge.crt` → `OK`.
2. `openssl x509 -in edge.crt -noout -text` → read issuer chain, SANs, EKU.
3. Explain why the server sends leaf+intermediate but not the root.

## Lab 6 — MITM (→ [`06-mitm.md`](06-mitm.md))
1. `docker compose --profile mitm up -d mitm`.
2. `curl --cacert ca-chain.crt https://localhost:8090/orders` → rejected.
3. `curl -k https://localhost:8090/orders` → succeeds; `docker compose logs mitm`
   shows the intercepted plaintext.

## Lab 7 — Load balancing & version management (LTM)
1. Manager: switch backend **v1 → v2**; refresh the Frontend — orders now show
   an `amount_with_tax` field. That's a live blue/green version flip.
2. `docker compose up -d --scale backend=4`; watch the **internal LB stats**
   (`:8404`) show 4 healthy servers in `backend_pool` sharing the load.
3. Manager: set **backend latency = 800ms** or **error rate = 0.3**; watch the
   LB stats sessions/errors and the `backend` logs react (fault injection).

## Lab 8 — Put it together
With traffic running and `v2` active, kill a replica
(`docker compose rm -sf backend-1` style) and watch: the LB health check ejects
it, the sniffer shows RSTs, the log viewer shows retries — then bring it back
and watch it rejoin the pool. Narrate every layer you can now name.
