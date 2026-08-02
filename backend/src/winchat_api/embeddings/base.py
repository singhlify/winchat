"""The provider-agnostic embedding interface.

Two methods, not one, because they are not interchangeable: several open models (including
nomic-embed) are trained with asymmetric prefixes — documents and queries must be encoded
differently or retrieval quality silently degrades. Baking that into the interface means a
call site cannot get it wrong.

`model_id` is carried explicitly so ingestion can stamp every stored vector with the model
that produced it. Querying a pgvector table with vectors from a different model returns
plausible-looking nonsense; the stamp is what lets us detect that instead of debugging bad
answers later.
"""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    model_id: str

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed corpus chunks (offline ingestion path)."""
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Embed a user question (request path)."""
        ...


class EmbeddingError(RuntimeError):
    """An embedding call failed. Raised with a message safe to show in /readyz."""
