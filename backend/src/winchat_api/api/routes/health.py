"""Health endpoints. `/healthz` is liveness and makes no external calls;
`/readyz` checks every dependency.
"""

import asyncio
import time
from typing import Literal

import asyncpg
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from winchat_api import __version__
from winchat_api.config import Settings, get_settings
from winchat_api.embeddings.registry import get_embedding_provider
from winchat_api.llm.base import Message
from winchat_api.llm.registry import get_chat_provider
from winchat_api.retrieval.rerank.registry import get_reranker

router = APIRouter(tags=["health"])

CheckStatus = Literal["ok", "error", "not_configured"]

# Environments where the deployment-hardening checks below do not apply. Everything NOT in
# this set is treated as a real deployment. The safe direction to be wrong in, since a new
# env name like "staging" then gets checked rather than silently exempted.
NON_DEPLOYED_ENVS = frozenset({"local", "test", "ci", "dev", "development"})


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


# A prompt roughly the size of a real one: system rules plus six retrieved passages plus a
# question is ~3-5k tokens. The probe used to send the single word "ping".
_LLM_PROBE = "Answer with the single word OK. " + ("Context passage. " * 320)


async def _check_llm() -> DependencyCheck:
    """A representative generation, not a trivial one. See the note above."""
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
            [Message(role="user", content=_LLM_PROBE)], max_tokens=4
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


async def _check_reranker() -> DependencyCheck:
    """Report which reranker is actually live.

    This exists because of a real incident: the API was started before a Cohere key was added to
    .env, settings are cached per process, and it ran for a whole session with reranking
    silently off. Answering "the sources do not mention it" for questions the corpus does
    answer. Retrieval recall differs by 17 points between those two states, and nothing surfaced
    the difference.
    """
    settings = get_settings()
    configured = settings.rerank_provider
    reranker = get_reranker()

    if configured == "none":
        return DependencyCheck(status="not_configured", detail="reranking disabled by config")

    if reranker.name == "none":
        # Asked for a reranker and did not get one, almost always a missing key, or a
        # process started before the key was added.
        return DependencyCheck(
            status="error",
            provider=configured,
            detail=f"{configured} requested but inactive. Check the API key, then restart",
        )

    return DependencyCheck(status="ok", provider=reranker.name, model=reranker.model)


async def _check_database(pool: asyncpg.Pool | None) -> DependencyCheck:
    """Query the corpus itself.

    `select 1` would only prove the socket is open. Counting indexed chunks proves the schema
    exists and the corpus was actually ingested. An empty index is a working database and a
    broken assistant, and readiness should not call that healthy.
    """
    settings = get_settings()
    if not settings.database_url:
        return DependencyCheck(status="not_configured", detail="DATABASE_URL is not set")
    if pool is None:
        return DependencyCheck(status="error", detail="database pool failed to open at startup")

    started = time.perf_counter()
    try:
        chunks = await pool.fetchval("select count(*) from faq_chunks")
        answers = await pool.fetchval("select count(*) from faq_answers")
    except Exception as exc:
        return DependencyCheck(status="error", detail=str(exc)[:300])

    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    if not chunks:
        return DependencyCheck(
            status="error",
            latency_ms=latency_ms,
            detail="no chunks indexed. Run winchat_api.ingestion.run",
        )
    return DependencyCheck(
        status="ok",
        provider="postgres",
        latency_ms=latency_ms,
        detail=f"{answers} answers, {chunks} chunks",
    )


def _check_config() -> DependencyCheck:
    """Settings that are safe locally and dangerous in production.

    A dependency check answers "can I reach it". This one answers "am I configured the way a
    deployed service must be", a different question, and one nothing else asks.
    """
    settings = get_settings()
    if settings.app_env in NON_DEPLOYED_ENVS:
        return DependencyCheck(status="ok", detail=f"{settings.app_env}, deployment checks skipped")

    problems: list[str] = []

    # The salt is what makes an anonymous subject unguessable. With the shipped default it is
    # public knowledge, so anyone can compute the hash for a given IP, enough to confirm
    # whether someone used the service, and to reason about the counter keyspace.
    if settings.rate_limit_salt == Settings.model_fields["rate_limit_salt"].default:
        problems.append("RATE_LIMIT_SALT is still the built-in default. Set a random value")

    # Behind a proxy, `request.client.host` is the PROXY's address, identical for everyone.
    # With this off in production, every anonymous visitor hashes to the same subject and
    # shares one 20-per-hour budget. The first user of the hour locks out the rest.
    if not settings.trust_proxy_headers:
        problems.append(
            "TRUST_PROXY_HEADERS is off, behind a proxy every visitor shares one "
            "rate-limit identity"
        )

    # An allowlist that still names localhost in production is either a forgotten setting
    # or a frontend that cannot talk to this API. Both are worth surfacing.
    if any("localhost" in origin for origin in settings.cors_origins):
        problems.append("CORS_ALLOW_ORIGINS still contains localhost")

    if problems:
        return DependencyCheck(status="error", detail="; ".join(problems))
    return DependencyCheck(status="ok", detail="production settings look right")


@router.get("/readyz", response_model=ReadinessResponse)
async def readyz(request: Request, response: Response) -> ReadinessResponse:
    """Readiness: every configured dependency answered a real call."""
    settings = get_settings()

    llm, embeddings, reranker, database = await asyncio.gather(
        _check_llm(),
        _check_embeddings(),
        _check_reranker(),
        _check_database(getattr(request.app.state, "db_pool", None)),
    )
    checks = {
        "config": _check_config(),
        "llm": llm,
        "embeddings": embeddings,
        "reranker": reranker,
        "database": database,
    }
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
