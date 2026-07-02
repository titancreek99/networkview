# Man-in-the-Middle (MITM)

A MITM attacker sits between client and server, terminating the client's TLS
with **their own** certificate and re-originating a second connection to the
real server. If the client validates certificates properly, the attack fails at
the handshake. If it doesn't, the attacker reads and can modify everything.

```
   client ──TLS(attacker cert)──▶  mitmproxy  ──TLS(real cert)──▶  lb-edge
                                     │
                                 sees & can alter cleartext
```

## The lab exercise

The `mitm` service (mitmproxy) runs as a reverse proxy in front of `lb-edge`.
It's opt-in:

```bash
docker compose --profile mitm up -d mitm     # listens on https://localhost:8090
```

Now run the same request two ways:

```bash
docker compose exec manager cat /certs/ca-chain.crt > ca-chain.crt

# 1) Client VALIDATES against our Root CA  -> attack DETECTED
curl --cacert ca-chain.crt https://localhost:8090/orders
#   curl: (60) SSL certificate problem: unable to get local issuer certificate
#   (mitmproxy's cert is NOT signed by our Root CA, so the chain won't build)

# 2) Client SKIPS validation (-k)  -> attack SUCCEEDS
curl -k https://localhost:8090/orders
#   returns the real response...
docker compose logs mitm            # ...and mitmproxy logged the full plaintext
```

## What each outcome teaches

- **Case 1** is the entire point of PKI (see
  [`05-certificate-signing.md`](05-certificate-signing.md)): the attacker can
  forge a cert *claiming* to be `lb-edge`, but can't get it **signed by a CA the
  client trusts**. Chain validation is the defense.
- **Case 2** shows how a single careless flag (`-k`, `verify=False`,
  `rejectUnauthorized:false`, a trusted-but-attacker-controlled CA) collapses
  all of TLS's protection. The handshake still "succeeds" and looks green — the
  failure is in *trust*, not crypto.

## Watch it in the sniffer

With the `mitm` proxy running, capture the client→mitm and mitm→edge legs and
confirm there are now **two** separate TLS sessions with **two different**
certificates — the tell-tale signature of interception. In the real world,
**certificate pinning** and monitoring for unexpected issuers are how you catch
this.

## Related real-world attacks this models

- **Rogue Wi-Fi / ARP spoofing** putting an attacker on-path.
- **Corporate TLS inspection** — the *sanctioned* version of MITM: IT installs
  its CA in every device's trust store, so its proxy's certs validate (Case 1
  becomes Case 2 by policy). Same mechanism, different intent.
- **SSL-stripping** — downgrading `https://` links to `http://`; defended by
  HSTS. Try it here: browse `http://localhost:8080` and note there's no
  transport security at all.
