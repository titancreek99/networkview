# HTTP vs HTTPS

**HTTP** is plaintext application data over TCP. **HTTPS** is the *exact same*
HTTP, but running inside a TLS session that provides:

- **Confidentiality** — the bytes are encrypted; a sniffer sees ciphertext.
- **Integrity** — AEAD ciphers detect tampering; a flipped bit breaks the record.
- **Authentication** — the server proves its identity with a certificate.

Note that HTTPS ≠ "secure app". It secures the *transport*. Anything that
terminates TLS (a load balancer, a CDN, a proxy) sees plaintext again.

## The lab is built to show this contrast

The edge LB exposes the **same frontend** three ways:

| URL | Transport | In the sniffer |
|---|---|---|
| `http://localhost:8080` | HTTP (cleartext) | full request line, headers, JSON body readable |
| `https://localhost:8443` | HTTPS / TLS 1.3 | only handshake + `Application Data` (encrypted) |
| `https://localhost:8444` | HTTPS / TLS 1.2 | handshake (+ visible cert) + encrypted data |

And critically: **TLS is terminated at the edge**. Everything *behind* it —
frontend→middleware→backend — is plain HTTP on purpose. So even when a user
connects over HTTPS, the internal hops are cleartext.

## See it in this lab

1. Manager → **Start** traffic.
2. Sniffer → **`edge`** capture → **HTTP (cleartext)** view. You can read the
   `GET /orders` requests and JSON responses that came in over **port 8080**.
   Switch to the **TLS handshake** view and note that the 8443/8444 traffic is
   *not* readable as HTTP — it's encrypted.
3. Now pick the **`internal`** capture → **HTTP (cleartext)** view. Here you can
   read the frontend→middleware and middleware→backend requests **in full**,
   even though the user came in over HTTPS. Click a packet to see the complete
   headers and body.

CLI:

```bash
# Cleartext - everything is on the wire
curl -v http://localhost:8080/orders

# Encrypted - same response, but the transport is protected
docker compose exec manager cat /certs/ca-chain.crt > ca-chain.crt
curl -v --cacert ca-chain.crt https://localhost:8443/orders
```

## The lesson: "internal = trusted" is a myth

The `internal` capture proves that an attacker who lands *anywhere* inside your
network can read all inter-service traffic if it's plain HTTP. This is the
motivation for **mutual TLS / zero-trust**: encrypt and authenticate every hop,
not just the edge. Try enabling internal TLS as an exercise (re-encrypt in the
`lb-int` config) and watch the `internal` capture go dark.
