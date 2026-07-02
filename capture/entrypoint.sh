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
set -eu

NAME="${CAP_NAME:-capture}"
FILTER="${CAP_FILTER:-}"
mkdir -p /pcaps

echo "[capture:${NAME}] starting on all interfaces, filter='${FILTER}'"

# -U  flush each packet (so the sniffer can read files while they grow)
# -G  rotate every 30s,  -W 20 keep a 20-file ring (~10 min of history) so a
#     freshly-completed, decodable capture shows up in the sniffer quickly
# -s 0 full packet payloads so we can read TLS ClientHello + HTTP bodies
exec tcpdump -i any -U -s 0 -G 30 -W 20 \
    -w "/pcaps/${NAME}_%Y-%m-%d_%H-%M-%S.pcap" \
    ${FILTER}
