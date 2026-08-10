"""The embedding interface. Documents and queries are separate methods because several open
models are trained with asymmetric prefixes.
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
