"""Health endpoints.

Two endpoints, deliberately separate:

* ``/healthz`` — liveness. Answers "is this process up?" with zero external calls, so a
  platform health check never fails because a third party is slow. This is what the host
  (Render) should poll.
* ``/readyz`` — readiness. Actually exercises every configured dependency with a real
  call. Slower, and intended for humans and deploy gates, not for a 5-second liveness probe.

A dependency that is not configured reports ``not_configured`` — never ``ok``. Locally that
is expected (we are mid-build) and readiness still returns 200 as ``degraded``. Anywhere
other than ``local`` it is a failure: a deployed app missing its API key is not ready, and a
health check that lies about that is worse than no health check.
"""

import asyncio
import time
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

from winchat_api import __version__
from winchat_api.config import get_settings
from winchat_api.embeddings.registry import get_embedding_provider
from winchat_api.llm.base import Message
from winchat_api.llm.registry import get_chat_provider

router = APIRouter(tags=["health"])

CheckStatus = Literal["ok", "error", "not_configured"]


class LivenessResponse(BaseModel):
    status: str
    service: str
    version: str
    env: str


class DependencyCheck(BaseModel):
    status: CheckStatus
    provider: str | None = None
    model: str | None = None
    latency_ms: float | None = None
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    version: str
    env: str
    checks: dict[str, DependencyCheck]


@router.get("/healthz", response_model=LivenessResponse)
async def healthz() -> LivenessResponse:
    """Liveness: the process is running and can serve a request. No external calls."""
    settings = get_settings()
    return LivenessResponse(
        status="ok",
        service="winchat-api",
        version=__version__,
        env=settings.app_env,
    )


async def _check_llm() -> DependencyCheck:
    """Smallest possible real generation — proves credentials, network, and model name."""
    settings = get_settings()
    if settings.llm_provider == "groq" and not settings.groq_api_key:
        return DependencyCheck(
            status="not_configured",
            provider=settings.llm_provider,
            detail="GROQ_API_KEY is not set",
        )

    started = time.perf_counter()
    try:
        provider = get_chat_provider()
        completion = await provider.complete(
            [Message(role="user", content="ping")], max_tokens=1
        )
    except Exception as exc:
        return DependencyCheck(
            status="error", provider=settings.llm_provider, detail=str(exc)[:300]
        )

    return DependencyCheck(
        status="ok",
        provider=completion.provider,
        model=completion.model,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
    )


async def _check_embeddings() -> DependencyCheck:
    """Embed one token and report the dimensionality the vector schema must match."""
    settings = get_settings()
    started = time.perf_counter()
    try:
        provider = get_embedding_provider()
        vector = await provider.embed_query("ping")
    except Exception as exc:
        return DependencyCheck(
            status="error", provider=settings.embedding_provider, detail=str(exc)[:300]
        )

    return DependencyCheck(
        status="ok",
        provider=provider.name,
        model=provider.model_id,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
        detail=f"dim={len(vector)}",
    )


async def _check_database() -> DependencyCheck:
    settings = get_settings()
    if not settings.database_url:
        return DependencyCheck(
            status="not_configured", detail="DATABASE_URL is not set (wired in Phase 2)"
        )
    # Phase 2 replaces this with a real `SELECT 1` plus a pgvector extension check.
    return DependencyCheck(status="not_configured", detail="connection check not implemented yet")


@router.get("/readyz", response_model=ReadinessResponse)
async def readyz(response: Response) -> ReadinessResponse:
    """Readiness: every configured dependency answered a real call."""
    settings = get_settings()

    llm, embeddings, database = await asyncio.gather(
        _check_llm(), _check_embeddings(), _check_database()
    )
    checks = {"llm": llm, "embeddings": embeddings, "database": database}
    statuses = {check.status for check in checks.values()}

    if "error" in statuses:
        status: Literal["ok", "degraded", "error"] = "error"
    elif "not_configured" in statuses:
        status = "degraded"
    else:
        status = "ok"

    # Outside local development, an unconfigured dependency means "not ready", not "fine".
    if status == "error" or (status == "degraded" and settings.app_env != "local"):
        response.status_code = 503

    return ReadinessResponse(
        status=status, version=__version__, env=settings.app_env, checks=checks
    )
