"""Ollama embedding provider — the local default (open weights, no vendor call).

Gotcha this class exists to absorb: Ollama's `nomic-embed-text` Modelfile template is a
bare `{{ .Prompt }}` passthrough, so it does NOT apply nomic's task prefixes for you. The
model was trained with `search_document:` / `search_query:`; omitting them costs retrieval
quality without raising an error anywhere. We apply them here so no caller has to know.
"""

from collections.abc import Sequence

import httpx

from winchat_api.embeddings.base import EmbeddingError, EmbeddingProvider

# Models trained with asymmetric task prefixes. Anything not listed gets no prefix.
_TASK_PREFIXES: dict[str, tuple[str, str]] = {
    "nomic-embed-text": ("search_document: ", "search_query: "),
}


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        timeout_s: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model_id = model
        self._base_url = base_url.rstrip("/")
        # `client` is an injection point for tests; production always builds its own.
        self._client = client or httpx.AsyncClient(base_url=self._base_url, timeout=timeout_s)
        # Tag lookup ignores an explicit ":latest" so "nomic-embed-text:latest" still matches.
        family = model.split(":", 1)[0]
        self._doc_prefix, self._query_prefix = _TASK_PREFIXES.get(family, ("", ""))

    async def _embed(self, inputs: list[str]) -> list[list[float]]:
        try:
            response = await self._client.post(
                "/api/embed", json={"model": self.model_id, "input": inputs}
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise EmbeddingError(
                f"ollama: {exc.response.status_code} {exc.response.text[:200]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"ollama: cannot reach {self._base_url} ({exc})") from exc

        embeddings = response.json().get("embeddings")
        if not embeddings or len(embeddings) != len(inputs):
            raise EmbeddingError("ollama: response did not contain one embedding per input")
        return embeddings

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._embed([f"{self._doc_prefix}{t}" for t in texts])

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([f"{self._query_prefix}{text}"]))[0]

    async def aclose(self) -> None:
        await self._client.aclose()
