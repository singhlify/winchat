"""Reading a signed-in user's saved conversations.

The endpoint that makes an account worth having. Conversations were already written for
signed-in users, and there was no way to read them back — so the history existed, belonged
to the account, and could only be reached from the device that happened to hold its id in
`localStorage`. From any second device it was invisible.

**Authentication is required, not optional, and that is the only place in this API where
that is true.** Everything else works anonymously on purpose, because the FAQ is public.
These rows are not public: they are one person's questions.

Isolation is enforced by Row Level Security through `user_scoped`, not by a `where user_id
= ...` in these handlers. That distinction is the whole design — application-level
filtering is one forgotten clause away from a cross-tenant leak, and it is the exact risk
OWASP names in LLM08 for shared stores.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from winchat_api.chat.history import list_conversations, load_conversation
from winchat_api.security.auth import AuthenticatedUser, require_user
from winchat_api.security.origin import require_browser_origin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["conversations"])

SignedInUser = Annotated[AuthenticatedUser, Depends(require_user)]


def _pool(request: Request):
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database is not available")
    return pool


class ConversationSummary(BaseModel):
    id: str
    title: str | None
    question_count: int
    created_at: str
    updated_at: str


class ConversationList(BaseModel):
    conversations: list[ConversationSummary]


class StoredTurn(BaseModel):
    role: str
    content: str
    # The retrieval trace, so citations survive the round trip and a restored conversation
    # looks like the one the user had rather than a plain transcript.
    trace: dict | None = None
    created_at: str


class ConversationDetail(BaseModel):
    id: str
    turns: list[StoredTurn]


@router.get(
    "/conversations",
    response_model=ConversationList,
    dependencies=[Depends(require_browser_origin)],
)
async def get_conversations(request: Request, user: SignedInUser) -> ConversationList:
    pool = _pool(request)
    rows = await list_conversations(pool, user.id)
    return ConversationList(
        conversations=[
            ConversationSummary(
                id=str(row["id"]),
                title=row["title"],
                question_count=row["question_count"] or 0,
                created_at=row["created_at"].isoformat(),
                updated_at=row["updated_at"].isoformat(),
            )
            for row in rows
        ]
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
    dependencies=[Depends(require_browser_origin)],
)
async def get_conversation(
    request: Request, conversation_id: str, user: SignedInUser
) -> ConversationDetail:
    pool = _pool(request)
    rows = await load_conversation(pool, user.id, conversation_id)

    # An id belonging to someone else returns no rows, because RLS filtered them out — so
    # "not yours" and "does not exist" are indistinguishable here, deliberately. Answering
    # 403 for one and 404 for the other would confirm which ids exist.
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return ConversationDetail(
        id=conversation_id,
        turns=[
            StoredTurn(
                role=row["role"],
                content=row["content"],
                trace=row["trace"],
                created_at=row["created_at"].isoformat(),
            )
            for row in rows
        ],
    )
