"""Embeddings over an OpenAI-compatible `/v1/embeddings` endpoint.

The deployment counterpart to the Ollama provider. Ollama is ideal locally — free, open
weights, nothing leaves the machine — but it needs a GPU-less container with the model
resident, which does not fit a small backend instance. Several hosts serve the *same open
weights* behind the OpenAI embeddings shape, so one client covers all of them and the
choice of host stays a config line.

The critical invariant: **the model here must be the same one the corpus was ingested
with.** A query embedded by a different model lands somewhere unrelated in the vector
space, and the failure is silent — retrieval returns confident nonsense rather than an
error. `faq_chunks.embedding_model` records what was used, and the ingestion pipeline
re-embeds when it changes.
"""

from collections.abc import Sequence

import httpx

from winchat_api.embeddings.base import EmbeddingError, EmbeddingProvider

# Same asymmetric-prefix problem as the Ollama provider: hosted endpoints pass the text
# through verbatim, so the task prefixes are still ours to add.
_TASK_PREFIXES: dict[str, tuple[str, str]] = {
    "nomic-embed-text": ("search_document: ", "search_query: "),
    "nomic-embed-text-v1.5": ("search_document: ", "search_query: "),
}


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url:
            raise EmbeddingError("EMBEDDING_BASE_URL is not set")
        if not api_key:
            raise EmbeddingError("EMBEDDING_API_KEY is not set")

        self.model_id = model
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout_s,
            headers={"authorization": f"Bearer {api_key}"},
        )
        family = model.split("/")[-1]
        self._doc_prefix, self._query_prefix = _TASK_PREFIXES.get(family, ("", ""))

    async def _embed(self, inputs: list[str]) -> list[list[float]]:
        try:
            response = await self._client.post(
                "/embeddings", json={"model": self.model_id, "input": inputs}
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise EmbeddingError(
                f"{self.name}: {exc.response.status_code} {exc.response.text[:200]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"{self.name}: cannot reach {self._base_url} ({exc})") from exc

        payload = response.json().get("data") or []
        if len(payload) != len(inputs):
            raise EmbeddingError(f"{self.name}: expected {len(inputs)} embeddings")

        # The spec allows results out of order; each carries its own index.
        ordered = sorted(payload, key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in ordered]

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._embed([f"{self._doc_prefix}{text}" for text in texts])

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([f"{self._query_prefix}{text}"]))[0]

    async def aclose(self) -> None:
        await self._client.aclose()
