"""The chat endpoint — Server-Sent Events (a one-way stream of updates over plain HTTP).

Streaming is not decoration. A grounded answer takes a second or two of retrieval before the
first token exists; without streaming the user stares at nothing for the whole generation.
"""

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from winchat_api.chat.history import load_history, save_turn
from winchat_api.chat.service import ChatTurn, plan_answer, stream_answer
from winchat_api.config import get_settings
from winchat_api.embeddings.registry import get_embedding_provider
from winchat_api.llm.base import ProviderError
from winchat_api.llm.registry import build_chat_provider, get_chat_provider
from winchat_api.retrieval.rerank.registry import get_reranker
from winchat_api.security.auth import AuthenticatedUser, optional_user
from winchat_api.security.identity import client_ip, is_maintenance_request, subject_for
from winchat_api.security.origin import require_browser_origin
from winchat_api.security.rate_limit import check_limits, record_usage
from winchat_api.security.turnstile import verify_turnstile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


class HistoryTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    # Bounded on purpose: an unbounded prompt is a cost attack (OWASP LLM10) before it is
    # a quality problem. Per-subject rate limits sit alongside this.
    message: str = Field(min_length=1, max_length=2000)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=20)
    conversation_id: str | None = None
    # Validated against the allowlist below — never passed to the provider as given.
    model: str | None = Field(default=None, max_length=100)


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _error_event(message: str, exc: Exception) -> str:
    """A user-facing error, with the provider's own text kept server-side.

    Upstream errors are not safe to forward verbatim: a Groq rate-limit body, for one, contains
    the organisation id and the account's quota. The full exception is logged; the client gets a
    sentence it can act on.
    """
    text = str(exc).lower()

    if isinstance(exc, ProviderError) and "rate limit" in text:
        # A per-minute limit clears in seconds; a daily quota does not clear until the window
        # rolls. Telling someone to "try again shortly" when the answer is "tomorrow" wastes
        # their time and makes the app look broken rather than capped.
        daily = any(k in text for k in ("per day", "tokens per day", "tpd", "daily"))
        detail = (
            "Today's free usage limit has been reached. It resets within 24 hours; "
            "picking a different model in the composer may work in the meantime."
            if daily
            else "Too many questions in the last minute. Try again in a few seconds."
        )
    elif isinstance(exc, ProviderError):
        detail = "The language model could not be reached."
    else:
        detail = "Something went wrong answering that. Please try again."

    return _sse("error", {"message": message, "detail": detail})


CurrentUser = Annotated[AuthenticatedUser | None, Depends(optional_user)]


@router.post("/chat", dependencies=[Depends(require_browser_origin)])
async def chat(request: Request, body: ChatRequest, user: CurrentUser) -> StreamingResponse:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database is not available")

    # Anonymous callers must prove they are a browser; signed-in ones already did that when
    # they authenticated. Checked before retrieval and before the model, like the rate limit,
    # so a rejected request costs nothing.
    if user is None:
        await verify_turnstile(request, client_ip=client_ip(request))

    subject = subject_for(request, user)

    # Checked before retrieval and before the model: a rejected request should cost
    # nothing beyond two indexed counts.
    decision = await check_limits(
        pool, subject, bypass_subject_limits=is_maintenance_request(request)
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail=decision.reason,
            headers={"Retry-After": str(decision.retry_after_s)},
        )
    await record_usage(pool, subject)

    # An unrecognised model is rejected outright rather than quietly falling back to the
    # default: silently answering with a different model than the caller asked for would make
    # any comparison between models meaningless.
    if body.model and body.model not in get_settings().allowed_models:
        raise HTTPException(status_code=400, detail=f"unsupported model: {body.model}")

    llm = build_chat_provider(model=body.model) if body.model else get_chat_provider()
    embedder = get_embedding_provider()
    reranker = get_reranker()

    # A signed-in user's history comes from the database, not from the request body — a
    # client that can invent its own history can invent assistant turns to steer the model.
    if user and body.conversation_id:
        history = await load_history(pool, user.id, body.conversation_id)
    else:
        history = [ChatTurn(role=turn.role, content=turn.content) for turn in body.history]

    async def event_stream() -> AsyncIterator[str]:
        try:
            plan = await plan_answer(
                pool=pool,
                llm=llm,
                embedder=embedder,
                reranker=reranker,
                question=body.message,
                history=history,
            )
        except Exception as exc:
            logger.exception("retrieval failed")
            yield _error_event("Could not search the FAQ.", exc)
            return

        retrieval = plan.retrieval
        yield _sse(
            "sources",
            {
                "search_query": plan.search_query,
                "citations": [asdict(citation) for citation in plan.citations],
                "reranker": retrieval.reranker if retrieval else "none",
                "rerank_skipped_reason": retrieval.rerank_skipped_reason if retrieval else None,
                # Refusal is surfaced, not hidden. A user who is told "I don't know" deserves
                # to see that the system searched and what it nearly matched.
                "refused": plan.refused,
                "refusal": asdict(plan.refusal) if plan.refusal else None,
                "near_misses": [asdict(citation) for citation in plan.near_misses],
            },
        )

        collected: list[str] = []
        try:
            async for token in stream_answer(llm, plan):
                collected.append(token)
                yield _sse("token", {"text": token})
        except Exception as exc:
            # The stream has already started, so an HTTP error code is no longer available.
            # The client renders this event instead of silently truncating.
            logger.exception("generation failed mid-stream")
            yield _error_event("The answer could not be completed.", exc)
            return

        conversation_id = body.conversation_id
        if user:
            conversation_id = await save_turn(
                pool,
                user.id,
                conversation_id=body.conversation_id,
                question=body.message,
                answer="".join(collected),
                plan=plan,
            )

        yield _sse(
            "done",
            {
                "model": llm.model,
                "provider": llm.name,
                "conversation_id": conversation_id,
                "timings_ms": plan.timings,
                "candidates": {
                    "dense": retrieval.dense_count if retrieval else 0,
                    "lexical": retrieval.lexical_count if retrieval else 0,
                    "fused": retrieval.fused_count if retrieval else 0,
                },
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # stops nginx-style proxies buffering the stream
            "X-RateLimit-Limit": str(decision.limit),
            "X-RateLimit-Remaining": str(max(0, decision.limit - decision.used - 1)),
        },
    )
