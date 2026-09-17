FROM oven/bun:1.3.10-slim AS gbrain-builder

ARG GBRAIN_VERSION=0.45.12.0
ARG GBRAIN_COMMIT=7fdcd8bd2ee0b3546b167da14cddd27eb2507212

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/gbrain
COPY scripts/gbrain-russian-output.patch /tmp/gbrain-russian-output.patch
RUN git init \
    && git remote add origin https://github.com/garrytan/gbrain.git \
    && git fetch --depth=1 origin "${GBRAIN_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && grep -q "\"version\": \"${GBRAIN_VERSION}\"" package.json \
    && git apply --check /tmp/gbrain-russian-output.patch \
    && git apply /tmp/gbrain-russian-output.patch
RUN bun install --frozen-lockfile \
    && bun run build \
    && ./bin/gbrain --version

FROM python:3.12-slim

ARG GBRAIN_VERSION=0.45.12.0
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    LIBRARY_GBRAIN_VERSION=${GBRAIN_VERSION}

WORKDIR /app

COPY --from=gbrain-builder /opt/gbrain/bin/gbrain /usr/local/bin/gbrain
COPY pyproject.toml README.md /app/
COPY src /app/src
COPY scripts /app/scripts
RUN pip install --no-cache-dir . \
    && gbrain --version

RUN mkdir -p /data/library

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c 'import os, urllib.request; urllib.request.urlopen("http://127.0.0.1:" + os.getenv("PORT", "8000") + "/healthz")'

CMD ["sh", "-c", "exec uvicorn main:app --app-dir src --host 0.0.0.0 --port ${PORT:-8000}"]
