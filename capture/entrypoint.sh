#!/bin/sh
# tcpdump capture sidecar.
#
# Runs inside another container's network namespace (network_mode:
# "service:<target>") so "-i any" sees every packet that service sends or
# receives - i.e. the traffic BETWEEN applications. Writes rotating pcap files
# to the shared /pcaps volume where the sniffer service decodes them.
#
#   CAP_NAME   - prefix for the pcap filenames (e.g. edge, internal, db)
#   CAP_FILTER - optional BPF filter (e.g. "tcp", "port 5432")
#
# This entrypoint is deliberately noisy and does NOT crash-loop silently: if
# tcpdump can't start (missing NET_RAW/NET_ADMIN, no interface, read-only
# volume) it prints why and stays alive so `docker compose logs cap-<x>` and
# the status file below make the failure obvious.
NAME="${CAP_NAME:-capture}"
FILTER="${CAP_FILTER:-}"
STATUS="/pcaps/_${NAME}.status"

log(){ echo "[capture:${NAME}] $*"; }

# 1) Prove the shared volume is writable (rules out mount/RO problems).
if ! mkdir -p /pcaps 2>/dev/null || ! : > "$STATUS" 2>/dev/null; then
  log "FATAL: cannot write to /pcaps volume (mount missing or read-only)"
  sleep 3600; exit 1
fi
echo "starting $(date -u +%FT%TZ)" > "$STATUS"

# 2) Show what we can see, for diagnostics.
log "tcpdump: $(tcpdump --version 2>&1 | head -1)"
log "interfaces visible in this netns:"
tcpdump -D 2>&1 | sed 's/^/[capture:'"${NAME}"'] /' || true
log "starting capture, filter='${FILTER}', writing /pcaps/${NAME}_<ts>.pcap"

# 3) Run tcpdump; if it ever exits, record why and stay alive for inspection.
#  -U  packet-buffered so files are readable while they grow
#  -G 30 rotate every 30s, -W 20 keep a 20-file ring (~10 min)
#  -s 0 full payloads so TLS ClientHello + HTTP bodies are captured
while : ; do
  tcpdump -i any -U -s 0 -G 30 -W 20 \
    -w "/pcaps/${NAME}_%Y-%m-%d_%H-%M-%S.pcap" \
    ${FILTER} 2> "/pcaps/_${NAME}.err"
  rc=$?
  log "tcpdump exited rc=${rc}; last error:"
  sed 's/^/[capture:'"${NAME}"'] /' "/pcaps/_${NAME}.err" 2>/dev/null | tail -5
  echo "tcpdump exited rc=${rc} at $(date -u +%FT%TZ)" >> "$STATUS"
  log "retrying in 5s (fix caps/interface, then it self-heals)"
  sleep 5
done
