"""Thumbs up and thumbs down on an answer."""

import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from winchat_api.api.routes.chat import CurrentUser
from winchat_api.security.identity import subject_for
from winchat_api.security.origin import require_browser_origin
from winchat_api.security.rate_limit import check_limits, record_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["feedback"])


class FeedbackRequest(BaseModel):
    vote: Literal["up", "down"]
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(min_length=1, max_length=20_000)
    conversation_id: str | None = None
    model: str | None = Field(default=None, max_length=100)
    # The retrieval trace as the client saw it. Bounded, because an unbounded JSON blob
    # from a client is a storage attack.
    trace: dict | None = None


class FeedbackResponse(BaseModel):
    recorded: bool


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    dependencies=[Depends(require_browser_origin)],
)
async def submit_feedback(
    request: Request,
    body: FeedbackRequest,
    user: CurrentUser,
) -> FeedbackResponse:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database is not available")

    subject = subject_for(request, user)
    decision = await check_limits(pool, subject)
    if not decision.allowed:
        raise HTTPException(status_code=429, detail=decision.reason)

    trace = json.dumps(body.trace)[:20_000] if body.trace else None

    try:
        await pool.execute(
            """
            insert into answer_feedback
                (user_id, conversation_id, vote, question, answer, trace, model)
            values ($1, $2, $3, $4, $5, $6, $7)
            """,
            user.id if user else None,
            body.conversation_id,
            body.vote,
            body.question,
            body.answer,
            trace,
            body.model,
        )
    except Exception:
        # Losing a vote is not worth showing the user an error over, they already got
        # their answer, and the feedback UI has no recovery to offer.
        logger.exception("could not record feedback")
        return FeedbackResponse(recorded=False)

    await record_usage(pool, subject)
    return FeedbackResponse(recorded=True)
