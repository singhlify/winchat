"""The two retrieval arms: dense (meaning) and lexical (exact terms).

Both are needed. Dense vectors have a *structural* failure on exact strings — course
codes, form numbers, "UWinsite" — that no better embedding model fixes, because a
fixed-length vector cannot encode exact string identity. Lexical search has the mirror
failure: it cannot match "how much does it cost" to "tuition fees". Hybrid is the floor,
not an optimization (RESEARCH.md §1).

On naming: Postgres full-text search with `ts_rank_cd` is not textbook BM25 — it has no
document-length saturation term. It fills the same role (exact-term matching) and, because
Reciprocal Rank Fusion consumes *ranks* rather than scores, the exact scoring function
matters far less than the ordering it produces. Calling it BM25 would be a lie that costs
nothing to avoid.
"""

import asyncpg

from winchat_api.retrieval.models import RetrievedChunk

_DENSE_SQL = """
    select c.id, c.a_id, c.content, a.question, a.url,
           1 - (c.embedding <=> $1) as score
    from faq_chunks c
    join faq_answers a on a.a_id = c.a_id
    order by c.embedding <=> $1
    limit $2
"""

# `plainto_tsquery` ANDs every term, which requires one chunk to contain all of them —
# "deadline to drop a course without penalty" then matches nothing at all. Rewriting the
# operators to OR restores recall, and `ts_rank_cd` still ranks chunks matching more terms
# higher. That is the right trade here because RRF consumes ranks: a weak one-word match
# lands deep in the list and contributes almost nothing to the fused score.
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
    """Nearest neighbours by cosine distance. `<=>` is pgvector's cosine operator."""
    rows = await pool.fetch(_DENSE_SQL, query_vector, limit)
    return _to_chunks(rows, "dense")


async def lexical_search(pool: asyncpg.Pool, query: str, limit: int) -> list[RetrievedChunk]:
    """Keyword match over the contextualized text (question + chunk)."""
    rows = await pool.fetch(_LEXICAL_SQL, query, limit)
    return _to_chunks(rows, "lexical")
