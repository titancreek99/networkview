FROM alpine:3.20
# Script is POSIX sh (busybox) + openssl only - no bash needed.
RUN apk add --no-cache openssl
COPY gen-certs.sh /usr/local/bin/gen-certs.sh
RUN chmod +x /usr/local/bin/gen-certs.sh
ENTRYPOINT ["/usr/local/bin/gen-certs.sh"]
