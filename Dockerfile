# Diagnostic Clank — local Archivist web service, portable container image.
# Build context is the repo root (this file's directory) since the app
# depends on two packages that live in sibling directories here.
FROM python:3.12-slim-bookworm

# Full Git SHA of the source this image was built from -- passed at build
# time (e.g. `--build-arg GIT_REVISION=$(git rev-parse HEAD)`, or via
# docker-compose.yml's build.args). Deliberately NOT derived from a .git
# directory at runtime -- no .git is copied into this image, and even if it
# were, the running container's filesystem is not proof of what was built.
# Mirrors the oem-radar/OEM Radar provenance convention: this becomes both
# the org.opencontainers.image.revision OCI label and the
# DIAGNOSTIC_CLANK_SOURCE_REVISION env var surfaced by `diagnostic-clank
# identity`. Never trust a checkout or tag alone -- compare all three.
ARG GIT_REVISION=unknown
LABEL clank.id="diagnostic-clank" \
      org.opencontainers.image.revision="${GIT_REVISION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DIAGNOSTIC_CLANK_SOURCE_REVISION=${GIT_REVISION} \
    DIAGNOSTIC_DATA_DIR=/app/data \
    DIAGNOSTIC_CLANK_BIND_HOST=127.0.0.1 \
    DIAGNOSTIC_CLANK_PORT=8420

WORKDIR /app

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin clank

COPY clank-runtime ./clank-runtime
COPY diagnostic-clank ./diagnostic-clank

RUN pip install --upgrade pip \
    && pip install ./clank-runtime ./diagnostic-clank \
    && mkdir -p /app/data \
    && chown -R clank:clank /app

USER clank

EXPOSE 8420

HEALTHCHECK --interval=60s --timeout=15s --start-period=20s --retries=3 \
    CMD ["python3", "-c", "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"DIAGNOSTIC_CLANK_PORT\"]}/healthz', timeout=5)"]

ENTRYPOINT ["python3", "/app/diagnostic-clank/native/docker/entrypoint.py"]
