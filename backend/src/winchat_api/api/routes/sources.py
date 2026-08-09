"""The source catalogue.

Every answer traces back to a published `ask.uwindsor.ca` article, and this endpoint exposes the
whole list. It earns trust, and it states the assistant's boundary honestly.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["sources"])

MAX_PAGE_SIZE = 1000


class Source(BaseModel):
    a_id: str
    question: str
    url: str
    lastmod: str | None = None
    chunks: int


class SourcesResponse(BaseModel):
    total: int
    returned: int
    sources: list[Source]


_SQL = """
    select a.a_id, a.question, a.url, a.lastmod, count(c.id) as chunks
    from faq_answers a
    left join faq_chunks c on c.a_id = a.a_id
    where ($1::text is null or a.question ilike '%' || $1 || '%')
    group by a.a_id, a.question, a.url, a.lastmod
    order by a.question
    limit $2 offset $3
"""


@router.get("/sources", response_model=SourcesResponse)
async def list_sources(
    request: Request,
    q: str | None = Query(default=None, max_length=200, description="filter by question text"),
    limit: int = Query(default=MAX_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
) -> SourcesResponse:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database is not available")

    # `q` is bound as a parameter and only ever used inside ilike. Never concatenated into
    # SQL. The % wildcards are added in the query, not taken from the user.
    rows = await pool.fetch(_SQL, q, limit, offset)
    total = await pool.fetchval(
        """
        select count(*) from faq_answers
        where ($1::text is null or question ilike '%' || $1 || '%')
        """,
        q,
    )

    return SourcesResponse(
        total=total or 0,
        returned=len(rows),
        sources=[
            Source(
                a_id=row["a_id"],
                question=row["question"],
                url=row["url"],
                lastmod=row["lastmod"].isoformat() if row["lastmod"] else None,
                chunks=row["chunks"],
            )
            for row in rows
        ],
    )
