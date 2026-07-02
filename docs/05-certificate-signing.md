# Certificate signing & the chain of trust

A TLS certificate is a public key + identity (subject, SANs) **signed by a
Certificate Authority**. Trust is transitive: you trust a small set of **Root
CAs**; they sign **Intermediate CAs**; intermediates sign **leaf** (server)
certs. Validating a cert means rebuilding and checking that chain up to a root
you already trust.

```
  NetworkView Root CA         (self-signed, in your trust store)
        │  signs
        ▼
  NetworkView Intermediate CA  (CA:TRUE, pathlen:0)   ← the "issuing" CA
        │  signs
        ▼
  edge / backend leaf certs    (CA:FALSE, EKU=serverAuth, SANs)
```

This lab builds exactly that chain in [`pki/gen-certs.sh`](../pki/gen-certs.sh).

## The signing mechanics (what the script does)

1. **Root CA**: `openssl req -x509` creates a *self-signed* cert
   (issuer == subject). It signs nothing but itself — it's the anchor.
2. **Intermediate**: generate a key → make a **CSR** (Certificate Signing
   Request: "here is my public key + who I claim to be") → the **Root signs the
   CSR** with `openssl x509 -req -CA rootCA.crt -CAkey rootCA.key`. The output
   is a cert whose *issuer* is the Root.
3. **Leaf**: same CSR flow, but signed by the **Intermediate**, and marked
   `basicConstraints=CA:FALSE`, `extendedKeyUsage=serverAuth`, plus
   `subjectAltName` (SANs) so hostname validation passes.

Why an intermediate at all? The root's private key is precious — kept offline.
Day-to-day issuance uses the intermediate, which can be revoked/rotated without
replacing the root in everyone's trust store. `pathlen:0` means "this
intermediate may sign leaves, but not further CAs."

## What the server presents

A server sends **leaf + intermediate** (its chain), but *not* the root — the
client already has the root. In this lab that bundle is `edge.pem`
(`leaf + intermediate + private key`), which is exactly what HAProxy loads.

## Verify it yourself

Certificates are generated into the `pki-data` volume. Extract and inspect:

```bash
docker compose exec manager sh -lc 'cat /certs/edge.crt' > edge.crt
docker compose exec manager sh -lc 'cat /certs/ca-chain.crt' > ca-chain.crt

# Rebuild the path and validate signatures:
openssl verify -CAfile ca-chain.crt edge.crt          # -> edge.crt: OK

# Read the leaf's identity, SANs and EKU:
openssl x509 -in edge.crt -noout -issuer -subject -ext subjectAltName,extendedKeyUsage

# Confirm the intermediate is a constrained CA:
docker compose exec manager sh -lc 'cat /certs/intermediateCA.crt' \
  | openssl x509 -noout -ext basicConstraints      # -> CA:TRUE, pathlen:0
```

Watch a live chain validation during a handshake:

```bash
openssl s_client -connect localhost:8443 -CAfile ca-chain.crt -servername lb-edge </dev/null \
  | grep -E "Verify return code|subject=|issuer="
# "Verify return code: 0 (ok)"  == the chain built successfully to a trusted root
```

## How this connects to MITM

An attacker can generate their own "edge" cert, but they **cannot get it signed
by our Root CA** (they don't have the root's private key). So a client that
validates the chain will reject the attacker's cert — that's the whole security
model. See [`06-mitm.md`](06-mitm.md) to watch it succeed and fail.
