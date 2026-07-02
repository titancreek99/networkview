# TLS 1.2 vs TLS 1.3

This lab exposes the **same app** over both versions so you can compare them on
the wire:

- `https://localhost:8443` → **TLS 1.3 only** (`lb-edge` bind `ssl-min-ver TLSv1.3`)
- `https://localhost:8444` → **TLS 1.2 only** (`ssl-min-ver TLSv1.2 ssl-max-ver TLSv1.2`)

## The headline differences

| | TLS 1.2 | TLS 1.3 |
|---|---|---|
| Handshake round-trips | 2-RTT | **1-RTT** (0-RTT possible on resume) |
| Cipher suite meaning | kx + auth + cipher + MAC (e.g. `ECDHE-RSA-AES128-GCM-SHA256`) | **AEAD cipher only** (e.g. `TLS_AES_128_GCM_SHA256`); key exchange moved to extensions |
| Key exchange | RSA *or* (EC)DHE — RSA kx has **no** forward secrecy | **(EC)DHE only** — forward secrecy always |
| Certificate message | sent in **cleartext** | sent **encrypted** (after ServerHello) |
| Legacy crypto (RC4, 3DES, SHA-1, static RSA, CBC) | allowed | **removed** |
| Negotiation of version | `ClientHello.version` field | `supported_versions` extension (the version field is frozen at 1.2 for middlebox compatibility) |

### Why 1.3 is one round-trip

In TLS 1.2 the client can't send a key share until it learns the server's chosen
parameters. In TLS 1.3 the client **guesses** the group and sends its
`key_share` already in the ClientHello; the server replies with its share in the
ServerHello and can send `Finished` immediately. Application data flows after a
single round-trip.

### Why the Certificate is hidden in 1.3

In 1.2 the `Certificate` message is before keys are established → visible to a
passive sniffer. In 1.3, everything after the ServerHello (including the
server's certificate) is already encrypted, so a passive observer sees *less*
about the server's identity. (The SNI in the ClientHello is still cleartext
unless Encrypted Client Hello / ECH is used.)

## See it in this lab

Capture both, then compare in the Sniffer:

```bash
docker compose exec manager cat /certs/ca-chain.crt > ca-chain.crt

# TLS 1.3
openssl s_client -connect localhost:8443 -CAfile ca-chain.crt -servername lb-edge -tls1_3 </dev/null | grep -E "Protocol|Cipher"
# TLS 1.2
openssl s_client -connect localhost:8444 -CAfile ca-chain.crt -servername lb-edge -tls1_2 </dev/null | grep -E "Protocol|Cipher"
```

In the Sniffer (`edge` capture, **TLS handshake** view) contrast the two:

- **1.2**: you'll see a `Certificate` handshake record as a distinct, readable
  packet, plus `Server Key Exchange`.
- **1.3**: after ServerHello the records show up as `Application Data` almost
  immediately — the certificate is *inside* the encrypted stream.

Try forcing a version the port doesn't allow and watch it fail — proof the LB is
really pinning versions:

```bash
openssl s_client -connect localhost:8443 -tls1_2 </dev/null   # 8443 is 1.3-only -> alert
```
