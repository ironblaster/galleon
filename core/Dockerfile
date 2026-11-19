# Base image pinned by digest (Dependabot keeps it fresh)
FROM python:3.15-alpine@sha256:0f9552bb28711333da16915ec146f5e6bb44a7fdac9ced15dc17c2e0206346dd

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
