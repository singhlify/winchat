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

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from winchat_api.chat.service import ChatTurn, plan_answer, stream_answer
from winchat_api.embeddings.registry import get_embedding_provider
from winchat_api.llm.registry import get_chat_provider
from winchat_api.retrieval.rerank.registry import get_reranker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


class HistoryTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    # Bounded on purpose: an unbounded prompt is a cost attack (OWASP LLM10) before it is
    # a quality problem. Hard limits here, per-user rate limits in Phase 6.
    message: str = Field(min_length=1, max_length=2000)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=20)


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database is not available")

    llm = get_chat_provider()
    embedder = get_embedding_provider()
    reranker = get_reranker()

    async def event_stream() -> AsyncIterator[str]:
        try:
            plan = await plan_answer(
                pool=pool,
                llm=llm,
                embedder=embedder,
                reranker=reranker,
                question=body.message,
                history=[ChatTurn(role=turn.role, content=turn.content) for turn in body.history],
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

        try:
            async for token in stream_answer(llm, plan):
                yield _sse("token", {"text": token})
        except Exception as exc:
            # The stream has already started, so an HTTP error code is no longer available.
            # The client renders this event instead of silently truncating.
            logger.exception("generation failed mid-stream")
            yield _sse("error", {"message": "Generation failed.", "detail": str(exc)[:200]})
            return

        yield _sse(
            "done",
            {
                "model": llm.model,
                "provider": llm.name,
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
        },
    )
