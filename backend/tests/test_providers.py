"""Provider tests. No network: the Ollama HTTP layer is stubbed with a mock transport."""

import json

import httpx
import pytest

from winchat_api.embeddings.base import EmbeddingError
from winchat_api.embeddings.ollama_provider import OllamaEmbeddingProvider
from winchat_api.embeddings.registry import _BUILDERS as EMBEDDING_BUILDERS
from winchat_api.llm.base import ProviderError
from winchat_api.llm.groq_provider import GroqChatProvider
from winchat_api.llm.registry import _BUILDERS as LLM_BUILDERS


def _stub_client(captured: list[dict]) -> httpx.AsyncClient:
    """An HTTP client that records requests and returns fixed-size embeddings."""

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured.append(payload)
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3] for _ in payload["input"]]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ollama.test")


async def test_nomic_task_prefixes_are_applied():
    """Ollama's template is a passthrough, so we must add nomic's prefixes ourselves."""
    captured: list[dict] = []
    provider = OllamaEmbeddingProvider(model="nomic-embed-text", client=_stub_client(captured))

    await provider.embed_documents(["a chunk"])
    await provider.embed_query("a question")

    assert captured[0]["input"] == ["search_document: a chunk"]
    assert captured[1]["input"] == ["search_query: a question"]


async def test_latest_tag_still_resolves_prefixes():
    captured: list[dict] = []
    provider = OllamaEmbeddingProvider(
        model="nomic-embed-text:latest", client=_stub_client(captured)
    )

    await provider.embed_query("a question")

    assert captured[0]["input"] == ["search_query: a question"]
    assert captured[0]["model"] == "nomic-embed-text:latest"


async def test_model_without_known_prefixes_is_left_alone():
    captured: list[dict] = []
    provider = OllamaEmbeddingProvider(model="mxbai-embed-large", client=_stub_client(captured))

    await provider.embed_query("a question")

    assert captured[0]["input"] == ["a question"]


async def test_empty_document_batch_makes_no_request():
    captured: list[dict] = []
    provider = OllamaEmbeddingProvider(model="nomic-embed-text", client=_stub_client(captured))

    assert await provider.embed_documents([]) == []
    assert captured == []


async def test_unreachable_ollama_raises_embedding_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    provider = OllamaEmbeddingProvider(
        model="nomic-embed-text",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://ollama.test"
        ),
    )

    with pytest.raises(EmbeddingError, match="cannot reach"):
        await provider.embed_query("a question")


def test_groq_provider_refuses_to_start_without_a_key():
    with pytest.raises(ProviderError, match="GROQ_API_KEY"):
        GroqChatProvider(api_key="", model="llama-3.3-70b-versatile")


def test_registries_expose_the_documented_defaults():
    """Guards the config contract: these strings appear in .env.example and the README."""
    assert "groq" in LLM_BUILDERS
    assert "ollama" in EMBEDDING_BUILDERS
