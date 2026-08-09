"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from winchat_api import __version__
from winchat_api.api.routes import chat, conversations, feedback, health, models, sources
from winchat_api.config import get_settings
from winchat_api.db.pool import create_pool
from winchat_api.embeddings.registry import get_embedding_provider

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the connection pool once per process, not once per request.

    A missing DATABASE_URL is not fatal here — the app still starts and `/readyz` reports the
    database as unconfigured. Refusing to boot would make the health endpoint that explains the
    problem unreachable.
    """
    settings = get_settings()
    app.state.db_pool = None

    # Logged at boot because .env changes need a restart to take effect, and a silently
    # inactive reranker costs 17 points of retrieval recall with no other symptom.
    from winchat_api.retrieval.rerank.registry import get_reranker

    reranker = get_reranker()
    if reranker.name == "none" and settings.rerank_provider != "none":
        logger.warning(
            "RERANK_PROVIDER=%s but no reranker is active — check the API key",
            settings.rerank_provider,
        )
    else:
        logger.info("reranker: %s (%s)", reranker.name, reranker.model)

    if settings.database_url:
        try:
            app.state.db_pool = await create_pool()
        except Exception:
            logger.exception("could not open the database pool; /readyz will report it")

    # Load the embedding model before serving. On a scale-to-zero host the alternative is
    # that the first user after a cold start waits for it on top of their own query.
    embedder = get_embedding_provider()
    warm = getattr(embedder, "warm", None)
    if warm is not None:
        try:
            await warm()
            logger.info("embeddings warm: %s", embedder.model_id)
        except Exception:
            logger.exception("could not warm the embedding model; first request will be slow")

    try:
        yield
    finally:
        if app.state.db_pool is not None:
            await app.state.db_pool.close()


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    app = FastAPI(
        title="WinChat API",
        version=__version__,
        description="Production RAG API for the UWindsor FAQ assistant.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(models.router)
    app.include_router(sources.router)
    app.include_router(feedback.router)
    app.include_router(conversations.router)
    return app


app = create_app()
