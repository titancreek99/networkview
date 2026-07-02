# NetworkView — a hands-on lab for TLS, TCP, MITM & PKI

A Dockerized, enterprise-shaped microservice stack built for **one purpose**:
to let you *practically* deep-dive the concepts below by watching real packets,
real TLS handshakes, and real certificates flow through a realistic topology.

> The application itself (a toy "orders shop") is deliberately boring. The
> **infrastructure around it** is the lesson.

## Concepts you can explore here

| Concept | Where to see it |
|---|---|
| **TCP handshake** (SYN / SYN-ACK / ACK) | Sniffer → *TCP handshake* view on any capture |
| **TLS handshake** (ClientHello/ServerHello/Cert) | Sniffer → *TLS handshake* on the `edge` capture |
| **TLS 1.2 vs TLS 1.3** | Hit `:8444` (1.2) vs `:8443` (1.3), compare ClientHellos |
| **HTTP vs HTTPS** | `:8080` (HTTP, fully readable) vs `:8443` (HTTPS, encrypted) |
| **Certificate signing** | `pki/gen-certs.sh` builds Root→Intermediate→leaf chain |
| **Man-in-the-Middle** | `mitm` profile — cert validation defeats it, `-k` doesn't |
| **Load balancing (LTM)** | HAProxy stats at `:8405`/`:8404`, replicas round-robined |

Full write-ups are in [`docs/`](docs/). Guided exercises: [`docs/labs.md`](docs/labs.md).
Driving it all from the admin console: [`docs/admin-guide.md`](docs/admin-guide.md).

## Architecture

```
                          ┌─────────── lb-edge (HAProxy / "LTM") ───────────┐
   browser / curl ──▶     │  :80  HTTP        :443 HTTPS(TLS1.3)            │
                          │  :8443 HTTPS(TLS1.2)      :8404 stats           │
                          └───────────────┬─────────────────────────────────┘
                                          │  (TLS terminated here)
                                     round-robin
                          ┌───────────────┴───────────┐
                        frontend-1                 frontend-2      (tier 1)
                          └───────────────┬───────────┘
                                          │  http  ──▶  lb-int :8081
                          ┌───────────────┴───────────┐
                       middleware-1              middleware-2      (tier 2)
                          └───────────────┬───────────┘
                                          │  http  ──▶  lb-int :8082
                          ┌───────────────┴───────────┐
                        backend-1                  backend-2       (tier 3)
                          └───────────────┬───────────┘
                                          │  psql
                                       postgres                    (data)

  control plane:  manager :9000   |   logviewer :9001   |   sniffer :9002
  packet capture: tcpdump sidecars on lb-edge, lb-int and db → shared pcap vol
```

Everything past the edge is **plaintext HTTP on purpose** — so you can read it
in the sniffer and understand why "internal traffic is trusted" is a myth.

## Quick start

```bash
# 1. Build and start the whole stack (Docker + Compose v2/v5 required)
docker compose up -d --build

# 2. Open the consoles
#    Frontend app .......... http://localhost:8080         (HTTP)
#                            https://localhost:8443        (HTTPS / TLS 1.3)
#                            https://localhost:8444        (HTTPS / TLS 1.2)
#    Manager (control) ..... http://localhost:9000
#    Log viewer ............ http://localhost:9001
#    Packet sniffer ........ http://localhost:9002
#    Edge LB stats ......... http://localhost:8405
#    Internal LB stats ..... http://localhost:8404

# 3. In the Manager: click "Start" traffic, then watch the sniffer & log viewer.
```

Trust the lab CA locally so browsers/curl accept the certs:

```bash
# The generated CA chain is in the pki-data volume; copy it out:
docker compose cp pki:/pki/out/ca-chain.crt ./ca-chain.crt   # if pki still exists
# or grab it from a running container that mounts /certs:
docker compose exec manager cat /certs/ca-chain.crt > ca-chain.crt

curl --cacert ca-chain.crt https://localhost:8443/orders     # HTTPS, verified
```

## Repository layout

```
pki/            Root/Intermediate/leaf certificate generation (cert signing)
services/
  common/       shared appkit: JSON logging, control store, Flask factory
  frontend/     tier-1 web UI
  middleware/   tier-2 BFF (plaintext hop to backend)
  backend/      tier-3 app + Postgres access
  manager/      control plane: versions, traffic gen, fault injection
  logviewer/    aggregated JSON log console
  sniffer/      tshark front-end over captured pcaps
lb/edge/        HAProxy edge config (TLS termination, HTTP/1.2/1.3)
lb/int/         HAProxy internal config (two pools)
capture/        tcpdump sidecar image
mitm/           man-in-the-middle exercise (mitmproxy)
db/             Postgres seed schema
docs/           concept deep-dives + guided labs
```

## Useful commands

```bash
docker compose ps                       # what's running
docker compose logs -f manager          # follow a service
docker compose up -d --scale backend=4  # more replicas -> watch LB spread load
docker compose --profile mitm up -d mitm
docker compose down -v                  # stop and wipe volumes (certs, pcaps, db)
```

## Teardown

```bash
docker compose down -v
```

See [`docs/labs.md`](docs/labs.md) for step-by-step exercises tied to each concept.
