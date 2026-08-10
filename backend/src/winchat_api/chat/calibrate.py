"""Reports where REFUSAL_MIN_DENSE_SCORE should sit for the current embedding model.

uv run python -m winchat_api.chat.calibrate
"""

import asyncio
import logging
import sys

from winchat_api.config import get_settings
from winchat_api.db.pool import create_pool
from winchat_api.embeddings.registry import get_embedding_provider
from winchat_api.retrieval.rerank.base import NoOpReranker
from winchat_api.retrieval.service import retrieve

ON_TOPIC = [
    "How much does it cost to replace a lost UwinCARD?",
    "What is the deadline to drop a course without penalty?",
    "How do I apply to a co-op program?",
    "Where do I pick up my student ID card?",
    "How do I pay my tuition fees?",
    "How do I request an official transcript?",
    "What scholarships can I apply for as a current student?",
    "How do I look up which classes are being offered?",
]

OFF_TOPIC = [
    "How do I bake sourdough bread?",
    "What is the capital of France?",
    "Who won the 2022 World Cup?",
    "How do I change a flat tire?",
    "Write me a Python function that sorts a list.",
    "What is the best ramen in Tokyo?",
    "How should I train for a marathon?",
]

# Scores like an on-topic question on every model tried. Kept out of the ranges above on
# purpose, see the module docstring.
ADVERSARIAL = "What are the admission requirements at the University of Toronto?"


async def score(pool, embedder, query: str) -> float:
    """Best dense similarity for one query. The reranker is irrelevant here: it reorders
    candidates, it does not change how close the closest one was."""
    result = await retrieve(pool=pool, embedder=embedder, reranker=NoOpReranker(), query=query)
    return result.best_dense_score


async def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    settings = get_settings()
    embedder = get_embedding_provider()
    pool = await create_pool(max_size=3)

    try:
        on = [(q, await score(pool, embedder, q)) for q in ON_TOPIC]
        off = [(q, await score(pool, embedder, q)) for q in OFF_TOPIC]
        adversarial = await score(pool, embedder, ADVERSARIAL)
    finally:
        await pool.close()

    print(f"embedding model: {embedder.model_id}\n")
    for label, rows in (("ON-TOPIC", on), ("OFF-TOPIC", off)):
        print(f"  {label}")
        for query, value in sorted(rows, key=lambda row: -row[1]):
            print(f"    {value:.4f}  {query[:64]}")
        print()

    lowest_on = min(value for _, value in on)
    highest_off = max(value for _, value in off)
    gap = lowest_on - highest_off

    print(f"  on-topic  range  {min(v for _, v in on):.4f} - {max(v for _, v in on):.4f}")
    print(f"  off-topic range  {min(v for _, v in off):.4f} - {max(v for _, v in off):.4f}")
    print(f"\n  adversarial (UofT) {adversarial:.4f}  <- expected to look on-topic; not a bug")

    if gap <= 0:
        print(
            f"\n  NO USABLE GAP: an off-topic query scored {highest_off:.4f}, at or above the "
            f"weakest on-topic query ({lowest_on:.4f}).\n"
            "  No single threshold separates these classes on this model. Do not pick"
            " one: fix retrieval or change the model."
        )
        return 1

    suggested = round((lowest_on + highest_off) / 2, 2)
    print(f"\n  usable gap       {highest_off:.4f} .. {lowest_on:.4f}  (width {gap:.4f})")
    print(f"  SUGGESTED        REFUSAL_MIN_DENSE_SCORE={suggested:.2f}")
    print(
        f"  margin           {suggested - highest_off:+.4f} above off-topic, "
        f"{lowest_on - suggested:+.4f} below on-topic"
    )
    print(f"  currently set to {settings.refusal_min_dense_score}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
