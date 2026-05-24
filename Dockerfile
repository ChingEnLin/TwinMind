# syntax=docker/dockerfile:1.7
#
# Multi-stage build for TwinMind.
#
# Stage 1 (builder): install Python deps via uv, pre-download the BGE-small
# embedder weights, and pre-build the Chroma index from data/samples/. We do
# the index build at image-build time (not at first request) so the cold-start
# path on Cloud Run is just "load the persistent index from disk" — no
# embedding pass at startup.
#
# Stage 2 (runtime): python:3.11-slim with only the deps, the BGE cache, the
# pre-built Chroma index, and the source code. Runs as a non-root user.
#
# Cloud Run sets $PORT; uvicorn binds to it. Health check on /v1/healthz.

ARG PYTHON_VERSION=3.11
ARG UV_VERSION=0.5.11

# ---------------------------------------------------------------- builder ---
FROM python:${PYTHON_VERSION}-slim AS builder

# uv is installed as a single static binary; faster than `pip install uv` and
# avoids polluting the runtime image with build tooling.
COPY --from=ghcr.io/astral-sh/uv:${UV_VERSION} /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_PYTHON_PREFERENCE=only-system \
    UV_NO_PROGRESS=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps first (cached layer when only source changes).
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Copy source and install the project itself (separate layer for fast iteration).
COPY src ./src
COPY data ./data
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Pre-download the BGE embedder so first request doesn't pay a model download.
# The cache lives under HOME; we set it explicitly so the path is stable across
# stages.
ENV HF_HOME=/app/.hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/app/.hf-cache
RUN .venv/bin/python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

# Build the Chroma index from data/samples/. Uses BGE (now cached) for
# embeddings; no Anthropic call required at this stage.
RUN .venv/bin/tm ingest --source local

# ---------------------------------------------------------------- runtime ---
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/app/.hf-cache \
    PATH=/app/.venv/bin:$PATH \
    PORT=8080

# Non-root user. Cloud Run doesn't require this but it's good hygiene.
RUN useradd --create-home --uid 1001 twinmind
WORKDIR /app

# Copy from builder: venv (with deps), source, pre-built Chroma index, BGE cache.
COPY --from=builder --chown=twinmind:twinmind /app/.venv /app/.venv
COPY --from=builder --chown=twinmind:twinmind /app/src /app/src
COPY --from=builder --chown=twinmind:twinmind /app/data /app/data
COPY --from=builder --chown=twinmind:twinmind /app/.hf-cache /app/.hf-cache
COPY --chown=twinmind:twinmind pyproject.toml /app/pyproject.toml

USER twinmind

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request, os, sys; \
sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8080\")}/v1/healthz', timeout=3).status == 200 else 1)" \
    || exit 1

# `sh -c` so $PORT (injected by Cloud Run) expands at runtime, not at build.
CMD ["sh", "-c", "uvicorn twin_mind.api.app:app --host 0.0.0.0 --port ${PORT}"]
