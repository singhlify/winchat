"""The chat endpoint — Server-Sent Events (a one-way stream of updates over plain HTTP).

Streaming is not decoration. A grounded answer takes a second or two of retrieval before
the first token exists; without streaming the user stares at nothing for the whole
generation. Sources are sent as their own event *before* any token, so the UI can render
citations while the text is still arriving.

SSE rather than WebSockets: the traffic is one-directional, and SSE survives proxies,
reconnects on its own, and needs no protocol upgrade.
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
from winchat_api.llm.registry import get_chat_provider
from winchat_api.retrieval.rerank.registry import get_reranker
from winchat_api.security.auth import AuthenticatedUser, optional_user
from winchat_api.security.rate_limit import (
    anonymous_subject,
    check_limits,
    record_usage,
    user_subject,
)

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


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _client_ip(request: Request) -> str:
    """The caller's address, trusting the proxy header only when configured to.

    Render and Vercel both sit in front of this service, so the socket address is the
    proxy's. `X-Forwarded-For` is client-supplied and trivially spoofed, which would let
    anyone mint a fresh rate-limit identity per request — so the leftmost entry is used
    only when a proxy is expected, and the direct address otherwise.
    """
    if get_settings().trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


CurrentUser = Annotated[AuthenticatedUser | None, Depends(optional_user)]


@router.post("/chat")
async def chat(request: Request, body: ChatRequest, user: CurrentUser) -> StreamingResponse:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database is not available")

    subject = user_subject(user.id) if user else anonymous_subject(_client_ip(request))

    # Checked before retrieval and before the model: a rejected request should cost
    # nothing beyond two indexed counts.
    decision = await check_limits(pool, subject)
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail=decision.reason,
            headers={"Retry-After": str(decision.retry_after_s)},
        )
    await record_usage(pool, subject)

    llm = get_chat_provider()
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
            yield _sse("error", {"message": "Retrieval failed.", "detail": str(exc)[:200]})
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
            yield _sse("error", {"message": "Generation failed.", "detail": str(exc)[:200]})
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
