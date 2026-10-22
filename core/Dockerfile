# Base image pinned by digest (Dependabot keeps it fresh)
FROM python:3.13-alpine@sha256:c50ccfb66e5cc97a610dcd0b9597de6ef5b52c96280b51997b353a0fc87a8361

LABEL org.opencontainers.image.title="Galleon" \
      org.opencontainers.image.description="The self-assembling media stack: seeds and wires Radarr, Sonarr, Prowlarr, qBittorrent, Jellyfin and Seerr" \
      org.opencontainers.image.source="https://github.com/ironblaster/galleon" \
      org.opencontainers.image.licenses="MIT"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY galleon_core /opt/galleon/galleon_core
COPY recyclarr.yml /opt/galleon/recyclarr.yml
WORKDIR /opt/galleon
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# Unprivileged by default; only the one-shot seed step runs as root (see compose.yaml)
USER 65534:65534
ENTRYPOINT ["python", "-m", "galleon_core"]
CMD ["bootstrap"]
