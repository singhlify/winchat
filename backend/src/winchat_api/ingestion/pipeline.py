"""The ingestion pipeline: corpus file → chunks → embeddings → pgvector.

Offline by design. Nothing here ever runs during a chat request — embedding documents
inside a request is the classic mistake this architecture is built to avoid.

Three properties worth calling out, because they are what separate a re-runnable pipeline
from a one-shot script:

* **Deletions are handled.** The corpus already shrank 558 → 556 mid-scrape. A pipeline
  that only upserts leaves answers in the index that the university has unpublished, and
  the assistant then cites content that no longer exists. Every run reconciles: any
  `a_id` absent from the corpus file is removed.
* **Unchanged answers are not re-embedded.** `content_hash` is compared, not `lastmod`,
  so a touched timestamp costs nothing while a real edit is caught.
* **A change of embedding model forces a re-embed.** Vectors from two models are not
  comparable, and mixing them degrades retrieval silently rather than raising.
"""

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import asyncpg

from winchat_api.embeddings.base import EmbeddingProvider
from winchat_api.ingestion.chunking import Chunk, chunk_answer
from winchat_api.ingestion.corpus import Answer, load_answers

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 32


@dataclass
class IngestionReport:
    total_answers: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    chunks_written: int = 0
    embedding_calls: int = 0
    duration_s: float = 0.0
    deleted_ids: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.total_answers} answers in corpus · "
            f"{self.inserted} new, {self.updated} changed, {self.unchanged} unchanged, "
            f"{self.deleted} deleted · {self.chunks_written} chunks written "
            f"({self.embedding_calls} embedding calls) in {self.duration_s:.1f}s"
        )


async def _existing_state(connection: asyncpg.Connection) -> dict[str, tuple[str, str | None]]:
    """Map a_id → (content_hash, embedding_model) for what is already indexed."""
    rows = await connection.fetch(
        """
        select a.a_id, a.content_hash, min(c.embedding_model) as embedding_model
        from faq_answers a
        left join faq_chunks c on c.a_id = a.a_id
        group by a.a_id, a.content_hash
        """
    )
    return {row["a_id"]: (row["content_hash"], row["embedding_model"]) for row in rows}


def _needs_work(answer: Answer, state: tuple[str, str | None] | None, model_id: str) -> bool:
    if state is None:
        return True
    content_hash, embedding_model = state
    # A missing embedding_model means the answer row exists but has no chunks — a previous
    # run died between the two writes. Treat it as work to do.
    return content_hash != answer.content_hash or embedding_model != model_id


async def _embed_chunks(
    provider: EmbeddingProvider, chunks: Sequence[Chunk], report: IngestionReport
) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]
        vectors.extend(await provider.embed_documents([chunk.context_text for chunk in batch]))
        report.embedding_calls += 1
    return vectors


async def _write_answer(
    pool: asyncpg.Pool,
    answer: Answer,
    chunks: Sequence[Chunk],
    vectors: Sequence[list[float]],
    model_id: str,
) -> None:
    """Replace an answer and all of its chunks atomically.

    Takes the pool, not a connection, and holds one only for the duration of the write.
    An earlier version held a single connection across the whole embedding loop and the
    pooler closed it out from under us — never hold a database connection across slow
    external I/O.

    Delete-then-insert rather than per-chunk upsert: an edit changes how the text splits,
    so chunk 4 of the old version has no relationship to chunk 4 of the new one. Matching
    them by index would leave stale text behind.
    """
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute(
            """
            insert into faq_answers (a_id, question, answer_text, url, lastmod,
                                     content_hash, fetched_at, ingested_at)
            values ($1, $2, $3, $4, $5, $6, $7, now())
            on conflict (a_id) do update set
                question     = excluded.question,
                answer_text  = excluded.answer_text,
                url          = excluded.url,
                lastmod      = excluded.lastmod,
                content_hash = excluded.content_hash,
                fetched_at   = excluded.fetched_at,
                ingested_at  = now()
            """,
            answer.a_id,
            answer.question,
            answer.answer_text,
            answer.url,
            answer.lastmod,
            answer.content_hash,
            answer.fetched_at,
        )
        await connection.execute("delete from faq_chunks where a_id = $1", answer.a_id)
        await connection.executemany(
            """
            insert into faq_chunks (a_id, chunk_index, content, context_text,
                                    token_estimate, embedding, embedding_model)
            values ($1, $2, $3, $4, $5, $6, $7)
            """,
            [
                (
                    chunk.a_id,
                    chunk.chunk_index,
                    chunk.content,
                    chunk.context_text,
                    chunk.token_estimate,
                    vector,
                    model_id,
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ],
        )


async def _reconcile_deletions(
    pool: asyncpg.Pool, live_ids: Sequence[str], report: IngestionReport
) -> None:
    """Remove answers the source has unpublished. Chunks go with them via cascade."""
    rows = await pool.fetch(
        "delete from faq_answers where a_id <> all($1::text[]) returning a_id", list(live_ids)
    )
    report.deleted = len(rows)
    report.deleted_ids = [row["a_id"] for row in rows]
    if rows:
        logger.info("removed %d answers no longer in the corpus", len(rows))


async def ingest(
    *,
    pool: asyncpg.Pool,
    provider: EmbeddingProvider,
    corpus_path: Path,
    force: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
) -> IngestionReport:
    started = time.perf_counter()
    report = IngestionReport()

    answers = load_answers(corpus_path)
    if limit is not None:
        answers = answers[:limit]
    report.total_answers = len(answers)
    logger.info("loaded %d answers from %s", len(answers), corpus_path)

    async with pool.acquire() as connection:
        state = await _existing_state(connection)

    pending = [
        answer
        for answer in answers
        if force or _needs_work(answer, state.get(answer.a_id), provider.model_id)
    ]
    report.unchanged = len(answers) - len(pending)
    report.inserted = sum(1 for answer in pending if answer.a_id not in state)
    report.updated = len(pending) - report.inserted

    if dry_run:
        stale = [a_id for a_id in state if a_id not in {answer.a_id for answer in answers}]
        report.deleted = len(stale)
        report.deleted_ids = stale
        report.duration_s = time.perf_counter() - started
        logger.info("dry run — no writes performed")
        return report

    for position, answer in enumerate(pending, start=1):
        chunks = chunk_answer(
            a_id=answer.a_id, question=answer.question, answer_text=answer.answer_text
        )
        if not chunks:
            logger.warning("answer %s produced no chunks; skipping", answer.a_id)
            continue

        vectors = await _embed_chunks(provider, chunks, report)
        await _write_answer(pool, answer, chunks, vectors, provider.model_id)
        report.chunks_written += len(chunks)

        if position % 50 == 0 or position == len(pending):
            logger.info("  %d/%d answers embedded", position, len(pending))

    # Only safe when the run covered the whole corpus; a --limit run sees a partial list
    # and would delete everything it did not look at.
    if limit is None:
        await _reconcile_deletions(pool, [answer.a_id for answer in answers], report)
    else:
        logger.info("skipping deletion reconcile because --limit was used")

    report.duration_s = time.perf_counter() - started
    return report
