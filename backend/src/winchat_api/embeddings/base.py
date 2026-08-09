"""The provider-agnostic embedding interface.

Two methods, not one, because they are not interchangeable: several open models (including
nomic-embed) are trained with asymmetric prefixes — documents and queries must be encoded
differently or retrieval quality silently degrades. Baking that into the interface means a call
site cannot get it wrong.
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
