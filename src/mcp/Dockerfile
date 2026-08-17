FROM ghcr.io/astral-sh/uv:0.12.5 AS uv

FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/app/.cache/uv

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app app

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

COPY src/mcp/pyproject.toml src/mcp/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY --chown=app:app src/mcp/app ./app
COPY --chown=app:app data/openapi.json ./openapi.json
RUN mkdir -p /app/.cache/uv && chown -R app:app /app/.cache

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000"]
