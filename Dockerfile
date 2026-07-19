# syntax=docker/dockerfile:1

FROM node:20-alpine AS frontend-builder

ENV CYPRESS_INSTALL_BINARY=0
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.8.17 AS uv-bin

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=uv-bin /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY README.md ./
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY --from=frontend-builder /build/frontend/dist ./frontend/dist
COPY examples/ ./examples/
COPY scripts/ ./scripts/

RUN groupadd --system --gid 10001 foundry \
    && useradd --system --uid 10001 --gid foundry --home-dir /app foundry \
    && mkdir -p /data/artifacts \
    && chown -R foundry:foundry /data /app

USER foundry
EXPOSE 8765

ENV DATASET_FOUNDRY_HOST=0.0.0.0 \
    DATASET_FOUNDRY_PORT=8765 \
    DATASET_FOUNDRY_DATA_DIR=/data \
    DATASET_FOUNDRY_DATABASE_URL=sqlite:////data/dataset-foundry.db \
    DATASET_FOUNDRY_ARTIFACT_DIR=/data/artifacts \
    DATASET_FOUNDRY_FRONTEND_DIST=/app/frontend/dist

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=2)"]

ENTRYPOINT ["/app/.venv/bin/dataset-foundry"]
CMD ["serve"]
