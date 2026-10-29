FROM ghcr.io/astral-sh/uv:0.11.31 AS uv
FROM python:3.13-slim-bookworm
COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /app
ENV UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY internal/ ./internal/
COPY cmd/ ./cmd/
RUN uv sync --frozen --no-dev --no-editable
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["geo-monitor-collector"]
CMD ["--config", "/config/collector.json"]
