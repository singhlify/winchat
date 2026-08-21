"""Provider tests. No network: the Ollama HTTP layer is stubbed with a mock transport."""

import json

import httpx
import pytest

from winchat_api.embeddings.base import EmbeddingError
from winchat_api.embeddings.cohere_provider import CohereEmbeddingProvider
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
        GroqChatProvider(api_key="", model="qwen/qwen3.6-27b")


def test_registries_expose_the_documented_defaults():
    """Guards the config contract: these strings appear in .env.example and the README."""
    assert "groq" in LLM_BUILDERS
    assert "ollama" in EMBEDDING_BUILDERS
    assert "cohere" in EMBEDDING_BUILDERS


# --- Cohere embeddings -------------------------------------------------------------


def _cohere_client(captured: list[dict], *, dimension: int = 1024) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured.append(payload)
        vectors = [[0.1] * dimension for _ in payload["texts"]]
        return httpx.Response(200, json={"embeddings": {"float": vectors}})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://cohere.test")


async def test_cohere_sends_the_asymmetric_input_types():
    """Documents and queries must be embedded as different task types or retrieval degrades
    silently, the same trap the nomic prefixes set, one layer up."""
    captured: list[dict] = []
    provider = CohereEmbeddingProvider(api_key="k", client=_cohere_client(captured))

    await provider.embed_documents(["a chunk"])
    await provider.embed_query("a question")

    assert captured[0]["input_type"] == "search_document"
    assert captured[1]["input_type"] == "search_query"


async def test_cohere_model_id_carries_the_dimension():
    """embed-v4.0 serves several widths from one model name, and vectors of different
    widths are not comparable. If model_id omitted the width, a dimension change would look
    like 'same model' to ingestion and quietly mix two spaces."""
    provider = CohereEmbeddingProvider(api_key="k", model="embed-v4.0", dimension=512)

    assert provider.model_id == "cohere/embed-v4.0/512"


async def test_cohere_batches_beyond_the_api_limit():
    """Cohere rejects a batch over 96 outright, so the provider splits rather than failing."""
    captured: list[dict] = []
    provider = CohereEmbeddingProvider(api_key="k", client=_cohere_client(captured))

    vectors = await provider.embed_documents([f"chunk {i}" for i in range(100)])

    assert len(captured) == 2
    assert [len(call["texts"]) for call in captured] == [96, 4]
    assert len(vectors) == 100


async def test_cohere_refuses_a_short_response():
    """Silently returning fewer vectors than chunks would misalign every one after it."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": {"float": [[0.1, 0.2]]}})

    provider = CohereEmbeddingProvider(
        api_key="k",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://cohere.test"
        ),
    )

    with pytest.raises(EmbeddingError, match="asked for 2 vectors"):
        await provider.embed_documents(["a", "b"])


async def test_cohere_provider_refuses_to_start_without_a_key():
    with pytest.raises(EmbeddingError, match="COHERE_API_KEY"):
        CohereEmbeddingProvider(api_key="")


async def test_cohere_gives_up_on_429_once_the_budget_is_gone():
    """A bounded wait, not an unbounded one, the request path cannot hang on a rate limit."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "rate limited"})

    provider = CohereEmbeddingProvider(
        api_key="k",
        retry_budget_s=0.0,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://cohere.test"
        ),
    )

    with pytest.raises(EmbeddingError, match="429"):
        await provider.embed_query("a question")
