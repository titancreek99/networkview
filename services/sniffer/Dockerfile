FROM python:3.12-slim
# tshark is only used to READ pcap files (tshark -r), so no capture privileges
# are needed. Suppress the setuid dumpcap prompt during install.
RUN echo "wireshark-common wireshark-common/install-setuid boolean false" | debconf-set-selections \
    && DEBIAN_FRONTEND=noninteractive apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tshark \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN pip install --no-cache-dir flask==3.0.3
COPY common/ /app/common/
COPY sniffer/ /app/sniffer/
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/sniffer/app.py"]
