#!/bin/sh
#
# gen-certs.sh - Build a small internal PKI to demonstrate CERTIFICATE SIGNING.
#
#   Root CA (self-signed, trust anchor)
#     └── Intermediate CA (signed by Root)          <- the "issuing" CA
#           └── server leaf certs (signed by Intermediate)
#
# The chain-of-trust is exactly what a real enterprise / public CA looks like:
# a browser trusts the Root, the server presents leaf + intermediate, the client
# builds the path leaf -> intermediate -> root and validates the signatures.
#
# All output lands in $OUT (a shared volume) so every other container can mount
# the certs it needs. Idempotent: if the leaf certs already exist we skip.
#
# POSIX sh (busybox ash) only + openssl - no bashisms, no process substitution,
# so it runs identically on the host and in a minimal Alpine container.

set -eu

OUT="${PKI_OUT:-/pki/out}"
DAYS=3650
mkdir -p "$OUT"
cd "$OUT"

log() { printf '[pki] %s\n' "$*"; }

# Fail loudly and early if openssl is missing (this is what "exit 127" means).
if ! command -v openssl >/dev/null 2>&1; then
  echo "[pki] FATAL: openssl not found on PATH" >&2
  exit 127
fi

if [ -f "$OUT/.done" ]; then
  log "certificates already generated - skipping (delete $OUT/.done to force regen)"
  exit 0
fi

# ---------------------------------------------------------------------------
# 1. ROOT CA  (self-signed: issuer == subject, this is the trust anchor)
# ---------------------------------------------------------------------------
log "generating Root CA private key (4096-bit RSA)"
openssl genrsa -out rootCA.key 4096 2>/dev/null

log "self-signing the Root CA certificate"
openssl req -x509 -new -nodes -key rootCA.key -sha256 -days "$DAYS" \
  -out rootCA.crt \
  -subj "/C=US/O=NetworkView Lab/OU=Security/CN=NetworkView Root CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null

# ---------------------------------------------------------------------------
# 2. INTERMEDIATE CA  (signed BY the root - this is real cert signing)
# ---------------------------------------------------------------------------
log "generating Intermediate CA private key"
openssl genrsa -out intermediateCA.key 4096 2>/dev/null

log "creating Intermediate CSR (Certificate Signing Request)"
openssl req -new -key intermediateCA.key \
  -out intermediateCA.csr \
  -subj "/C=US/O=NetworkView Lab/OU=Security/CN=NetworkView Intermediate CA" 2>/dev/null

log "Root CA SIGNS the Intermediate CSR -> intermediate certificate"
cat > int_ext.cnf <<'EOF'
basicConstraints=critical,CA:TRUE,pathlen:0
keyUsage=critical,keyCertSign,cRLSign
EOF
openssl x509 -req -in intermediateCA.csr \
  -CA rootCA.crt -CAkey rootCA.key -CAcreateserial \
  -out intermediateCA.crt -days "$DAYS" -sha256 \
  -extfile int_ext.cnf 2>/dev/null

# The chain a server should present: its own leaf first, then the intermediate.
# (The root is NOT sent on the wire; the client already has it in its trust store.)
cat intermediateCA.crt rootCA.crt > ca-chain.crt

# ---------------------------------------------------------------------------
# 3. LEAF (server) CERTIFICATES  - one per TLS-terminating service.
#    Each gets Subject Alternative Names so hostname validation passes for the
#    docker service name AND localhost.
# ---------------------------------------------------------------------------
sign_leaf() {
  name="$1"
  sans="$2"
  log "issuing leaf cert for '${name}' (SAN: ${sans})"

  openssl genrsa -out "${name}.key" 2048 2>/dev/null
  openssl req -new -key "${name}.key" -out "${name}.csr" \
    -subj "/C=US/O=NetworkView Lab/OU=Apps/CN=${name}" 2>/dev/null

  # Intermediate CA signs the leaf. serverAuth EKU = "this cert is a TLS server".
  cat > "leaf_${name}.cnf" <<EOF
basicConstraints=CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=${sans}
EOF
  openssl x509 -req -in "${name}.csr" \
    -CA intermediateCA.crt -CAkey intermediateCA.key -CAcreateserial \
    -out "${name}.crt" -days 825 -sha256 \
    -extfile "leaf_${name}.cnf" 2>/dev/null

  # HAProxy wants a single PEM: leaf + intermediate + private key.
  cat "${name}.crt" intermediateCA.crt "${name}.key" > "${name}.pem"
}

sign_leaf "edge"    "DNS:localhost,DNS:edge.lab,DNS:lb-edge,DNS:frontend,IP:127.0.0.1"
sign_leaf "backend" "DNS:backend,DNS:lb-int,DNS:localhost,IP:127.0.0.1"
sign_leaf "mitm"    "DNS:localhost,DNS:mitm,DNS:edge.lab,IP:127.0.0.1"

chmod -R a+r "$OUT"
touch "$OUT/.done"

log "PKI ready. Files in $OUT:"
ls -1 "$OUT"
log "Inspect with:  openssl x509 -in $OUT/edge.crt -noout -text"
