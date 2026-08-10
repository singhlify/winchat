"""The two retrieval arms: dense vector search and Postgres full-text search.

Both are needed. A fixed-length vector cannot encode exact string identity, so dense search
misses course codes and form numbers; lexical search cannot match a paraphrase.
"""

import asyncpg

from winchat_api.config import get_settings
from winchat_api.retrieval.models import RetrievedChunk

_DENSE_SQL = """
    select c.id, c.a_id, c.content, a.question, a.url,
           1 - (c.embedding <=> $1) as score
    from faq_chunks c
    join faq_answers a on a.a_id = c.a_id
    order by c.embedding <=> $1
    limit $2
"""

# `plainto_tsquery` ANDs every term, which requires one chunk to contain all of them,
# "deadline to drop a course without penalty" then matches nothing at all. Rewriting the
# operators to OR restores recall, and `ts_rank_cd` still ranks chunks matching more terms
# higher.
_LEXICAL_SQL = """
    with parsed as (
        select replace(plainto_tsquery('english', $1)::text, '&', '|')::tsquery as query
    )
    select c.id, c.a_id, c.content, a.question, a.url,
           ts_rank_cd(to_tsvector('english', c.context_text), parsed.query) as score
    from faq_chunks c
    join faq_answers a on a.a_id = c.a_id,
         parsed
    where parsed.query::text <> ''
      and to_tsvector('english', c.context_text) @@ parsed.query
    order by score desc
    limit $2
"""


def _to_chunks(rows, stage: str) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id=row["id"],
            a_id=row["a_id"],
            question=row["question"],
            content=row["content"],
            url=row["url"],
            scores={stage: float(row["score"])},
        )
        for row in rows
    ]


async def dense_search(
    pool: asyncpg.Pool, query_vector: list[float], limit: int
) -> list[RetrievedChunk]:
    """Nearest neighbours by cosine distance. `<=>` is pgvector's cosine operator, and `ef_search`
    must be at least `limit`, whose default of 40 is below this pipeline's dense limit.
    """
    settings = get_settings()
    # Never below the requested limit; the max() is the whole point of the setting.
    ef_search = max(settings.retrieval_hnsw_ef_search, limit)

    async with pool.acquire() as connection, connection.transaction():
        await connection.execute(f"set local hnsw.ef_search = {int(ef_search)}")
        rows = await connection.fetch(_DENSE_SQL, query_vector, limit)
    return _to_chunks(rows, "dense")


async def lexical_search(pool: asyncpg.Pool, query: str, limit: int) -> list[RetrievedChunk]:
    """Keyword match over the contextualized text (question + chunk)."""
    rows = await pool.fetch(_LEXICAL_SQL, query, limit)
    return _to_chunks(rows, "lexical")
