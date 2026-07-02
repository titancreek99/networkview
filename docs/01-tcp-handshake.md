# The TCP three-way handshake

Before any HTTP or TLS bytes flow, TCP must establish a connection. That setup
is the **three-way handshake**.

```
client                                   server
  │   SYN            seq=x               │   "I want to talk. My start seq is x."
  │ ───────────────────────────────────▶ │
  │   SYN, ACK       seq=y, ack=x+1      │   "OK. My start seq is y, I got your x."
  │ ◀─────────────────────────────────── │
  │   ACK            ack=y+1             │   "Got your y. Let's go."
  │ ───────────────────────────────────▶ │
  │  ── connection ESTABLISHED ──         │
```

Key ideas:

- **SYN** = *synchronize* sequence numbers. Each side picks a random Initial
  Sequence Number (ISN) so old/duplicated segments can't be confused with new
  data, and to make sequence prediction attacks harder.
- The ACK number is always *"the next byte I expect"* = the peer's seq + 1.
- Connection teardown is a separate 4-way exchange (**FIN / ACK / FIN / ACK**),
  or an abrupt **RST** (reset).
- The three RTTs of setup are pure latency before your first byte of data —
  which is exactly why TLS 1.3 and QUIC work so hard to cut round-trips.

## See it in this lab

1. In the Manager (`http://localhost:9000`) click **Start** traffic.
2. Open the Sniffer (`http://localhost:9002`), pick the **`edge_…`** capture and
   the **TCP handshake (SYN/ACK)** view.
3. You'll see rows with flags `S` (SYN), `S.` (SYN-ACK) and `.` (ACK). Click any
   packet for the full dissection — note the sequence/acknowledgement numbers,
   window size, MSS and other TCP options in the SYN.

CLI equivalent (from your host, capturing the published edge port):

```bash
# Watch just the handshake flags on the HTTP port
sudo tcpdump -i lo -n 'tcp port 8080 and (tcp[tcpflags] & (tcp-syn|tcp-fin|tcp-rst) != 0)'
curl http://localhost:8080/orders
```

## Why it matters for the other topics

TLS runs *on top of* an established TCP connection. So in every capture you'll
see the TCP handshake **first**, then (on the HTTPS ports) the TLS handshake,
then encrypted application data. Being able to tell the two handshakes apart is
the foundation for everything else in this lab.
