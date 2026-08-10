"""Compares recall and MRR with and without the configured reranker.

uv run python -m winchat_api.retrieval.rerank.check
"""

import asyncio
import json
import logging
import sys

import httpx

from winchat_api.config import BACKEND_ROOT, get_settings
from winchat_api.db.pool import create_pool
from winchat_api.embeddings.registry import get_embedding_provider
from winchat_api.retrieval.rerank.base import NoOpReranker, Reranker
from winchat_api.retrieval.rerank.registry import build_reranker
from winchat_api.retrieval.service import retrieve

logger = logging.getLogger(__name__)

GOLDEN = BACKEND_ROOT / "evals" / "golden" / "uwindsor.jsonl"

# Well past a trial key's one-minute window. A reranker that gives up on a 429 falls back to
# unranked order, which would measure the wrong system.
MEASUREMENT_RETRY_BUDGET_S = 120.0


async def cohere_rerank_models(api_key: str) -> list[str]:
    """Ask the account which rerank models it can actually use."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.cohere.com/v1/models",
                params={"endpoint": "rerank"},
                headers={"authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
        return sorted(model["name"] for model in response.json().get("models", []))
    except Exception as exc:
        logger.warning("could not list Cohere models: %s", exc)
        return []


async def measure(
    pool, embedder, reranker: Reranker, cases: list[dict]
) -> tuple[float, float, list[str]]:
    hits = 0
    reciprocal = 0.0
    misses: list[str] = []

    for case in cases:
        result = await retrieve(
            pool=pool, embedder=embedder, reranker=reranker, query=case["question"]
        )
        ranked = [chunk.a_id for chunk in result.chunks]
        expected = set(case["expected_a_ids"])
        rank = next((i for i, a_id in enumerate(ranked, start=1) if a_id in expected), None)
        if rank:
            hits += 1
            reciprocal += 1 / rank
        else:
            misses.append(case["id"])

    total = len(cases)
    return hits / total, reciprocal / total, misses


async def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()

    cases = [
        json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    scored = [case for case in cases if case.get("expected_a_ids")]

    if settings.rerank_provider == "cohere":
        if not settings.cohere_api_key:
            print("COHERE_API_KEY is not set, nothing to compare against.")
            return 2
        available = await cohere_rerank_models(settings.cohere_api_key)
        if available:
            mark = "ok" if settings.rerank_model in available else "NOT AVAILABLE"
            print(f"cohere rerank models: {', '.join(available)}")
            print(f"configured RERANK_MODEL={settings.rerank_model} -> {mark}\n")

    # Long enough to sit out a whole per-minute window rather than degrade to RRF order.
    reranker = build_reranker(settings, retry_budget_s=MEASUREMENT_RETRY_BUDGET_S)
    if reranker.name == "none":
        print("No reranker is active. Check RERANK_PROVIDER and the API key.")
        return 2

    pool = await create_pool(max_size=3)
    embedder = get_embedding_provider()
    try:
        base_recall, base_mrr, base_misses = await measure(pool, embedder, NoOpReranker(), scored)
        recall, mrr, misses = await measure(pool, embedder, reranker, scored)
    finally:
        await pool.close()

    print(f"{len(scored)} retrieval-scored cases, top_n={settings.retrieval_top_n}\n")
    print(f"{'':16} {'recall':>8} {'MRR':>8}")
    print(f"{'no reranker':16} {base_recall:>7.1%} {base_mrr:>8.3f}")
    print(f"{reranker.name + ' (' + reranker.model + ')':16}"[:16] + f" {recall:>7.1%} {mrr:>8.3f}")
    print(f"\n  baseline misses: {base_misses}")
    print(f"  reranked misses: {misses}")

    delta = recall - base_recall
    verdict = "HELPS" if delta > 0 else ("NO CHANGE" if delta == 0 else "HURTS")
    print(f"\n  recall {delta:+.1%}, MRR {mrr - base_mrr:+.3f}  ->  {verdict}")
    if delta < 0:
        print("  A reranker that lowers recall should not ship. Set RERANK_PROVIDER=none.")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
