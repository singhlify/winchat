"""Ask one question from the terminal, printing the answer and the sources behind it.

uv run python -m winchat_api.ask "how do I drop a course?"
"""

import asyncio
import logging
import sys

from winchat_api.chat.service import answer_question
from winchat_api.db.pool import create_pool
from winchat_api.embeddings.registry import get_embedding_provider
from winchat_api.llm.registry import get_chat_provider
from winchat_api.retrieval.rerank.registry import get_reranker


async def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)

    question = " ".join(sys.argv[1:])
    pool = await create_pool(max_size=4)
    try:
        answer = await answer_question(
            pool=pool,
            llm=get_chat_provider(),
            embedder=get_embedding_provider(),
            reranker=get_reranker(),
            question=question,
        )
    finally:
        await pool.close()

    print(f"Q: {question}\n")
    print(answer.text.strip())
    print("\nSources:")
    for citation in answer.plan.citations:
        print(f"  [{citation.index}] {citation.question}")
        print(f"      {citation.url}")

    retrieval = answer.plan.retrieval
    print(
        f"\nmodel={answer.model} reranker={retrieval.reranker if retrieval else 'none'} "
        f"tokens={answer.prompt_tokens}+{answer.completion_tokens}"
    )
    print(f"timings_ms={answer.plan.timings}")


if __name__ == "__main__":
    asyncio.run(main())
