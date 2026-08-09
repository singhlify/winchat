"""Ingestion CLI. uv run python -m winchat_api.ingestion.run --dry-run uv run python -m
winchat_api.ingestion.run uv run python -m winchat_api.ingestion.run --force # after changing
chunking.
"""

import argparse
import asyncio
import logging
from pathlib import Path

from winchat_api.config import get_settings
from winchat_api.db.pool import create_pool
from winchat_api.embeddings.registry import build_embedding_provider
from winchat_api.ingestion.pipeline import ingest

logger = logging.getLogger("ingestion")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest the FAQ corpus into pgvector.")
    parser.add_argument("--corpus", type=Path, default=None, help="path to answers.jsonl")
    parser.add_argument("--limit", type=int, default=None, help="only process the first N answers")
    parser.add_argument("--force", action="store_true", help="re-embed everything")
    parser.add_argument("--dry-run", action="store_true", help="report the plan, write nothing")
    return parser.parse_args()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # httpx logs every embedding call at INFO, which buries the progress lines.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = parse_args()
    settings = get_settings()

    # A long retry budget, unlike the request path: a hosted embedding endpoint meters per
    # minute and this run makes one call per answer, so hitting the limit is expected. The
    # right response is to wait, not to abort several hundred answers in.
    provider = build_embedding_provider(
        settings, retry_budget_s=settings.embedding_ingest_retry_budget_s
    )
    logger.info("embedding with %s / %s", provider.name, provider.model_id)

    pool = await create_pool(max_size=4)
    try:
        report = await ingest(
            pool=pool,
            provider=provider,
            corpus_path=args.corpus or settings.corpus_path,
            force=args.force,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    finally:
        await pool.close()

    logger.info(report.summary())
    if report.deleted_ids:
        logger.info("removed a_ids: %s", ", ".join(sorted(report.deleted_ids)))


if __name__ == "__main__":
    asyncio.run(main())
