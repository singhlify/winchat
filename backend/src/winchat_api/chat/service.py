"""The chat pipeline: question → (rewrite) → retrieve → build context → stream an answer."""

import logging
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field

import asyncpg

from winchat_api.chat.context import Citation, build_context
from winchat_api.chat.prompts import (
    NO_CONTEXT_MESSAGE,
    REWRITE_PROMPT,
    SYSTEM_PROMPT,
    build_user_message,
)
from winchat_api.chat.refusal import Refusal, should_refuse
from winchat_api.embeddings.base import EmbeddingProvider
from winchat_api.llm.base import ChatProvider, Message
from winchat_api.retrieval.rerank.base import Reranker
from winchat_api.retrieval.service import RetrievalResult, retrieve

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 6


@dataclass
class ChatTurn:
    role: str
    content: str


@dataclass
class AnswerPlan:
    """Everything decided before the first token is generated."""

    question: str
    search_query: str
    citations: list[Citation] = field(default_factory=list)
    retrieval: RetrievalResult | None = None
    messages: list[Message] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    refusal: Refusal | None = None
    # Shown to the user when refusing: what we did find, clearly labelled as not good
    # enough to answer from. Hiding it would make the refusal look like a broken search.
    near_misses: list[Citation] = field(default_factory=list)

    @property
    def refused(self) -> bool:
        return self.refusal is not None


async def rewrite_query(llm: ChatProvider, question: str, history: Sequence[ChatTurn]) -> str:
    """Make a follow-up self-contained: "how much is it?" means nothing to a search index.

    Skipped entirely on the first turn — an extra model call that cannot improve anything
    is pure latency. A failed rewrite falls back to the raw question rather than erroring;
    a slightly worse search beats no answer.
    """
    if not history:
        return question

    transcript = "\n".join(f"{turn.role}: {turn.content}" for turn in history[-MAX_HISTORY_TURNS:])
    try:
        completion = await llm.complete(
            [
                Message(role="system", content=REWRITE_PROMPT),
                Message(role="user", content=f"{transcript}\nuser: {question}"),
            ],
            temperature=0.0,
            max_tokens=100,
        )
    except Exception as exc:
        logger.warning("query rewrite failed, using the raw question: %s", exc)
        return question

    rewritten = completion.text.strip().strip('"')
    return rewritten or question


async def plan_answer(
    *,
    pool: asyncpg.Pool,
    llm: ChatProvider,
    embedder: EmbeddingProvider,
    reranker: Reranker,
    question: str,
    history: Sequence[ChatTurn] = (),
) -> AnswerPlan:
    started = time.perf_counter()
    search_query = await rewrite_query(llm, question, history)
    rewrite_ms = round((time.perf_counter() - started) * 1000, 1)

    retrieval = await retrieve(pool=pool, embedder=embedder, reranker=reranker, query=search_query)
    context = build_context(retrieval.chunks)

    refusal = should_refuse(retrieval)
    if refusal is not None:
        # The model is never called. Refusing costs no tokens and cannot hallucinate.
        logger.info(
            "refusing: %s (score=%.4f < %.2f)", refusal.reason, refusal.score, refusal.threshold
        )
        return AnswerPlan(
            question=question,
            search_query=search_query,
            citations=[],
            near_misses=context.citations[:3],
            retrieval=retrieval,
            messages=[],
            timings={"rewrite": rewrite_ms, **retrieval.latency_ms},
            refusal=refusal,
        )

    messages = [
        Message(role="system", content=SYSTEM_PROMPT),
        *[
            Message(role=turn.role, content=turn.content)  # type: ignore[arg-type]
            for turn in history[-MAX_HISTORY_TURNS:]
        ],
        Message(role="user", content=build_user_message(question, context.text)),
    ]

    return AnswerPlan(
        question=question,
        search_query=search_query,
        citations=context.citations,
        retrieval=retrieval,
        messages=messages,
        timings={"rewrite": rewrite_ms, **retrieval.latency_ms},
    )


async def stream_answer(llm: ChatProvider, plan: AnswerPlan) -> AsyncIterator[str]:
    if plan.refused:
        yield NO_CONTEXT_MESSAGE
        return

    async for token in llm.stream(plan.messages, temperature=0.1, max_tokens=800):
        yield token


@dataclass
class Answer:
    text: str
    plan: AnswerPlan
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


async def answer_question(
    *,
    pool: asyncpg.Pool,
    llm: ChatProvider,
    embedder: EmbeddingProvider,
    reranker: Reranker,
    question: str,
    history: Sequence[ChatTurn] = (),
) -> Answer:
    """Non-streaming answer.

    The same pipeline the streaming endpoint uses, collected into one value. The eval
    harness needs this: it scores complete answers, and it must score the code path the
    user actually gets, not a parallel implementation that can drift from it.
    """
    plan = await plan_answer(
        pool=pool,
        llm=llm,
        embedder=embedder,
        reranker=reranker,
        question=question,
        history=history,
    )
    if plan.refused:
        return Answer(text=NO_CONTEXT_MESSAGE, plan=plan, model=llm.model)

    started = time.perf_counter()
    completion = await llm.complete(plan.messages, temperature=0.1, max_tokens=800)
    plan.timings["generate"] = round((time.perf_counter() - started) * 1000, 1)

    return Answer(
        text=completion.text,
        plan=plan,
        model=completion.model,
        prompt_tokens=completion.prompt_tokens,
        completion_tokens=completion.completion_tokens,
    )
