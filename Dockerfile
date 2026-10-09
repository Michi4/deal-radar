FROM python:3.12-slim
# ---- opencode CLI (keyless fallback AI: muse-spark free tier), pinned source ----
FROM oven/bun:1.3-slim AS ocbuild
ARG OPENCODE_REF=687664c63b2bb4eb9b9c7e0dc37227869282ed80
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    python3 make g++ \
 && rm -rf /var/lib/apt/lists/*
RUN git init /oc && cd /oc && git remote add origin https://github.com/anomalyco/opencode \
 && git fetch --depth 1 origin $OPENCODE_REF && git checkout FETCH_HEAD
WORKDIR /oc
RUN bun install
WORKDIR /oc/packages/opencode
# OPENCODE_VERSION: the build stamps 0.0.0 from git tags (none fetched); the free
# tier requires >=1.18.0, so stamp the release-line version of this source (matches
# the distro 2.0.24 build of the same code — unmodified source, pinned commit above).
RUN OPENCODE_VERSION=2.0.24 bun run script/build.ts --single --skip-install && ls dist/*/bin/
FROM python:3.12-slim
COPY --from=ocbuild /oc/packages/opencode/dist/*/bin/opencode /usr/local/bin/opencode
RUN opencode --version
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu sqlite3 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -r -m app
WORKDIR /app
COPY pyproject.toml README.md ./
COPY packages packages/
COPY drivers drivers/
COPY apps apps/
COPY web-v2/dist web-v2/dist/
COPY marketplace marketplace/
RUN pip install --no-cache-dir -e .
ENV PYTHONPATH=/app/packages:/app/drivers:/app/apps DB_PATH=/data/dealradar.db
RUN mkdir -p /data && chown app:app /data
VOLUME /data
EXPOSE 8099
USER app
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8099/health',timeout=4)"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8099", "--app-dir", "apps"]
