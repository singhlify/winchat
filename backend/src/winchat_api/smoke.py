"""Smoke check: prove both providers really work, with visible output.

`/readyz` proves the wiring; this proves the behaviour — real generated text, and an embedding
space where related sentences actually sit closer together than unrelated ones. uv run python -m
winchat_api.smoke
"""

import asyncio
import math

from winchat_api.config import get_settings
from winchat_api.embeddings.registry import get_embedding_provider
from winchat_api.llm.base import Message
from winchat_api.llm.registry import get_chat_provider


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


async def check_embeddings() -> None:
    provider = get_embedding_provider()
    print(f"\n[embeddings] {provider.name} / {provider.model_id}")

    query = "How do I apply for a co-op work permit?"
    documents = [
        "Co-op work permit applications are submitted through the IRCC portal.",
        "The Leddy Library is open until 11pm during the exam period.",
    ]
    query_vector = await provider.embed_query(query)
    document_vectors = await provider.embed_documents(documents)

    print(f"  dim = {len(query_vector)}")
    print(f"  query: {query}")
    for text, vector in zip(documents, document_vectors, strict=True):
        print(f"  cos={cosine(query_vector, vector):.3f}  {text}")


async def check_llm() -> None:
    settings = get_settings()
    provider = get_chat_provider()
    print(f"\n[llm] {provider.name} / {settings.llm_model}")

    messages = [
        Message(role="system", content="Answer in one short sentence."),
        Message(role="user", content="What is retrieval-augmented generation?"),
    ]

    completion = await provider.complete(messages, max_tokens=60)
    print(f"  complete(): {completion.text.strip()}")
    print(f"  tokens: prompt={completion.prompt_tokens} completion={completion.completion_tokens}")

    print("  stream():   ", end="", flush=True)
    async for token in provider.stream(messages, max_tokens=60):
        print(token, end="", flush=True)
    print()


async def main() -> None:
    settings = get_settings()
    print(f"winchat-api smoke check (env={settings.app_env})")

    await check_embeddings()
    if settings.llm_provider == "groq" and not settings.groq_api_key:
        print("\n[llm] skipped — GROQ_API_KEY is not set in backend/.env")
    else:
        await check_llm()


if __name__ == "__main__":
    asyncio.run(main())
