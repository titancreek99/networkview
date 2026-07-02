# MITM lab (mitmproxy)

The `mitm` service runs [mitmproxy](https://mitmproxy.org) as a **reverse proxy
in front of the edge LB**, presenting its *own* certificate to clients while
transparently relaying to the real edge. It's the attacker sitting on the wire.

It is gated behind the `mitm` compose profile so it doesn't run by default:

```bash
docker compose --profile mitm up -d mitm
```

Then, from your host (or the manager container), compare the two outcomes that
define why TLS certificate validation matters:

```bash
# 1) Client validates the cert against our Root CA -> MITM is DETECTED.
#    The handshake fails because mitmproxy's cert is NOT signed by our CA.
curl --cacert pki/out/ca-chain.crt https://localhost:8090/orders
#    -> curl: (60) SSL certificate problem: unable to get local issuer certificate

# 2) Client skips validation (-k) -> MITM SUCCEEDS.
#    mitmproxy terminates TLS, reads/prints the plaintext, then re-encrypts
#    upstream. This is what happens when an app disables verification.
curl -k https://localhost:8090/orders
```

Watch `docker compose logs -f mitm` to see the intercepted plaintext request and
response — the whole point: **a valid TLS handshake is only as safe as the
client's willingness to verify the certificate chain.**
