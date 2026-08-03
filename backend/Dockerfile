# Backend container. Slim and boring on purpose — the anti-goals rule out orchestration,
# and a single well-built image is what a small Python service actually needs.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies are installed from the lockfile in their own layer, so editing source code
# does not reinstall the world on every build.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY src ./src
COPY migrations ./migrations
COPY evals ./evals
RUN uv sync --locked --no-dev

# Bake the embedding model into the image.
#
# Without this the first request after every cold start downloads ~280 MB before it can
# answer anything — on a scale-to-zero host that is most requests. Downloading it at build
# time makes the image bigger and the container start predictable, which is the right trade
# for a service that sleeps.
#
# It also removes a runtime dependency on Hugging Face being reachable: a model that is
# already on disk cannot fail to download.
ENV FASTEMBED_CACHE_DIR=/app/.fastembed
RUN uv run python -c "\
from fastembed import TextEmbedding; \
TextEmbedding(model_name='nomic-ai/nomic-embed-text-v1.5', cache_dir='/app/.fastembed')" \
    && du -sh /app/.fastembed

# Runs unprivileged: a container that does not need root should not have it.
RUN useradd --create-home --uid 10001 winchat && chown -R winchat:winchat /app
USER winchat

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# The platform health check should hit /healthz (liveness, no external calls), never
# /readyz — a readiness probe that calls third parties will restart the service whenever a
# provider has a slow minute.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"

CMD ["sh", "-c", "uvicorn winchat_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
