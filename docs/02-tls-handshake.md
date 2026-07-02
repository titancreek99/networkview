# The TLS handshake

Once TCP is established, TLS negotiates **which crypto to use** and
**authenticates the server** (and optionally the client), then derives the
symmetric keys used to encrypt the rest of the connection.

## TLS 1.2 handshake (2 round-trips)

```
client                                                 server
  │ ClientHello  (TLS versions, cipher suites, random) │
  │ ─────────────────────────────────────────────────▶ │
  │ ServerHello  (chosen cipher, random)               │
  │ Certificate  (server's cert chain)                 │
  │ ServerKeyExchange (e.g. ECDHE params, signed)      │
  │ ServerHelloDone                                    │
  │ ◀───────────────────────────────────────────────── │
  │ ClientKeyExchange (client's ECDHE pubkey)          │
  │ ChangeCipherSpec + Finished (now encrypted)        │
  │ ─────────────────────────────────────────────────▶ │
  │ ChangeCipherSpec + Finished                        │
  │ ◀───────────────────────────────────────────────── │
  │  ── application data (encrypted) ──                 │
```

The two things that always happen:

1. **Negotiation** — client offers a list, server picks one (cipher suite,
   TLS version, extensions). This is why the ClientHello is the single most
   interesting packet to inspect.
2. **Key agreement + authentication** — modern suites use **ECDHE**
   (Ephemeral Elliptic-Curve Diffie-Hellman) so both sides derive a shared
   secret that is *never sent on the wire*. The server signs the exchange with
   its certificate's private key, proving it owns the cert.

**Forward secrecy:** because ECDHE keys are ephemeral (thrown away after the
session), capturing the traffic today and stealing the server key tomorrow does
*not* let an attacker decrypt past sessions.

## What's visible vs. encrypted

Even on HTTPS, the early handshake is in cleartext on the wire:

| Visible to a sniffer | Encrypted |
|---|---|
| ClientHello (incl. SNI hostname, offered ciphers) | HTTP request/response |
| ServerHello (chosen cipher) | Cookies, credentials, bodies |
| **Certificate (TLS 1.2)** — server identity | Client cert (TLS 1.3) |

That's why in the sniffer you can still see *which site* and *what crypto*, but
not the actual data.

## See it in this lab

1. Start traffic in the Manager, open the Sniffer on the **`edge`** capture.
2. Use the **TLS handshake** view, then **TLS ClientHello**.
3. Click the ClientHello packet → in the full dissection scroll to
   `Handshake Protocol: Client Hello`. Read:
   - **Version** and the `supported_versions` extension
   - the **Cipher Suites** list the client offered
   - **Server Name Indication (SNI)** — the hostname in cleartext
4. Click the ServerHello to see the **single** cipher suite the server chose.

CLI deep-dive of a handshake:

```bash
docker compose exec manager cat /certs/ca-chain.crt > ca-chain.crt
openssl s_client -connect localhost:8443 -CAfile ca-chain.crt -servername lb-edge </dev/null
# Read: negotiated protocol/cipher, peer cert chain, "Verify return code: 0 (ok)"
```

Continue to [`03-tls12-vs-tls13.md`](03-tls12-vs-tls13.md) to compare the two
handshake shapes side by side.
