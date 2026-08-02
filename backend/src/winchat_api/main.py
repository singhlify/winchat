"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from winchat_api import __version__
from winchat_api.api.routes import chat, feedback, health, models, sources
from winchat_api.config import get_settings
from winchat_api.db.pool import create_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the connection pool once per process, not once per request.

    A missing DATABASE_URL is not fatal here — the app still starts and `/readyz` reports
    the database as unconfigured. Refusing to boot would make the health endpoint that
    explains the problem unreachable.
    """
    settings = get_settings()
    app.state.db_pool = None

    if settings.database_url:
        try:
            app.state.db_pool = await create_pool()
        except Exception:
            logger.exception("could not open the database pool; /readyz will report it")

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
    return app


app = create_app()
