FROM node:24-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.11.31 AS uv
FROM python:3.13-slim-bookworm
COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /app
ENV UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY internal/ ./internal/
COPY cmd/ ./cmd/
RUN uv sync --frozen --no-dev --no-editable
COPY --from=web /web/dist/ ./web/dist/
COPY deploy/collector.Dockerfile deploy/collector.compose.yaml ./deploy/
COPY scripts/ ./scripts/
RUN useradd --system --uid 10001 monitor && mkdir -p /app/data && chown -R monitor:monitor /app/data && chmod 700 /app/data
ENV PATH="/app/.venv/bin:$PATH" GEO_HOST=0.0.0.0 GEO_PORT=8000 GEO_PROJECT_DIRECTORY=/app GEO_DATABASE=/app/data/monitor.sqlite3
USER monitor
EXPOSE 8000
CMD ["geo-monitor-server"]
