FROM alpine:3.20
# Script is POSIX sh (busybox) + openssl only - no bash needed.
RUN apk add --no-cache openssl
COPY gen-certs.sh /usr/local/bin/gen-certs.sh
# Strip any CR (Windows CRLF) so the "#!/bin/sh" shebang is exec'able even when
# the repo was checked out on Windows with autocrlf; then mark executable.
RUN sed -i 's/\r$//' /usr/local/bin/gen-certs.sh && chmod +x /usr/local/bin/gen-certs.sh
ENTRYPOINT ["/usr/local/bin/gen-certs.sh"]
