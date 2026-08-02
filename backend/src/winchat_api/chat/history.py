"""Persisting conversations for signed-in users.

Every write goes through `user_scoped`, so Row Level Security is what actually enforces
ownership. The `user_id = $n` in these statements is belt-and-braces, not the control:
if someone later writes a query and forgets it, the policy still refuses the row.

Anonymous users get no history. Storing conversations for people we cannot authenticate
would mean holding chat logs against an IP hash — data we would then have to protect, for
a feature nobody asked for.
"""

import json
import logging
from dataclasses import dataclass

import asyncpg

from winchat_api.chat.service import Answer, AnswerPlan, ChatTurn
from winchat_api.db.session import user_scoped

logger = logging.getLogger(__name__)

TITLE_MAX_CHARS = 80


@dataclass(frozen=True, slots=True)
class StoredTurn:
    conversation_id: str


def _trace(plan: AnswerPlan) -> dict:
    """The retrieval trace, kept so an answer can be explained after the fact."""
    retrieval = plan.retrieval
    return {
        "search_query": plan.search_query,
        "citations": [
            {"index": c.index, "a_id": c.a_id, "url": c.url, "score": c.score}
            for c in plan.citations
        ],
        "refused": plan.refused,
        "refusal": (
            {
                "reason": plan.refusal.reason,
                "score": plan.refusal.score,
                "threshold": plan.refusal.threshold,
                "stage": plan.refusal.stage,
            }
            if plan.refusal
            else None
        ),
        "reranker": retrieval.reranker if retrieval else "none",
        "best_dense_score": retrieval.best_dense_score if retrieval else 0.0,
        "timings_ms": plan.timings,
    }


async def load_history(
    pool: asyncpg.Pool, user_id: str, conversation_id: str, *, limit: int = 12
) -> list[ChatTurn]:
    async with user_scoped(pool, user_id) as connection:
        rows = await connection.fetch(
            """
            select role, content from messages
            where conversation_id = $1
            order by created_at desc
            limit $2
            """,
            conversation_id,
            limit,
        )
    return [ChatTurn(role=row["role"], content=row["content"]) for row in reversed(rows)]


async def save_turn(
    pool: asyncpg.Pool,
    user_id: str,
    *,
    conversation_id: str | None,
    question: str,
    answer: str,
    plan: AnswerPlan,
) -> str | None:
    """Store the question and the answer. Returns the conversation id.

    Never raises into the request: the answer has already been delivered by the time this
    runs, and losing history is not a reason to show the user an error.
    """
    try:
        async with user_scoped(pool, user_id) as connection:
            if conversation_id is None:
                conversation_id = str(
                    await connection.fetchval(
                        """
                        insert into conversations (user_id, title)
                        values ($1, $2) returning id
                        """,
                        user_id,
                        question[:TITLE_MAX_CHARS],
                    )
                )
            else:
                await connection.execute(
                    "update conversations set updated_at = now() where id = $1 and user_id = $2",
                    conversation_id,
                    user_id,
                )

            await connection.executemany(
                """
                insert into messages (conversation_id, user_id, role, content, trace)
                values ($1, $2, $3, $4, $5)
                """,
                [
                    (conversation_id, user_id, "user", question, None),
                    (conversation_id, user_id, "assistant", answer, json.dumps(_trace(plan))),
                ],
            )
        return conversation_id
    except Exception:
        logger.exception("could not save conversation turn")
        return conversation_id


async def save_answer(
    pool: asyncpg.Pool, user_id: str, *, conversation_id: str | None, answer: Answer
) -> str | None:
    return await save_turn(
        pool,
        user_id,
        conversation_id=conversation_id,
        question=answer.plan.question,
        answer=answer.text,
        plan=answer.plan,
    )
