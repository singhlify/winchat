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
# README.md is copied because pyproject declares `readme = "README.md"`; without it
# hatchling fails metadata validation and the build dies with an unhelpful traceback.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --no-dev

COPY src ./src
COPY migrations ./migrations
COPY evals ./evals
RUN uv sync --locked --no-dev

# No embedding model is baked in, and `fastembed` is not installed.
#
# An earlier revision did both: it ran the nomic weights in-process and downloaded them at
# build time so a cold start would not. That image measured 920 MB, and every free
# container tier worth using caps at 512 MB — so the choice was a paid instance or hosted
# embeddings. Hosted won, and the model plus onnxruntime left with it.
#
# The trade, so nobody has to rediscover it: this container now depends on a third party
# being reachable to answer anything at all, where the old one only needed the network for
# the LLM. `/readyz` checks the embedding provider for exactly that reason.
#
# To go back, install the extra (`uv sync --locked --extra local`) and restore the bake
# step from git history. The provider is still in the tree and still tested.

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
