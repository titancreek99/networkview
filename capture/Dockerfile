FROM alpine:3.20
RUN apk add --no-cache tcpdump
COPY entrypoint.sh /entrypoint.sh
# Strip any CR (Windows CRLF) so the shebang is exec'able, then mark executable.
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
