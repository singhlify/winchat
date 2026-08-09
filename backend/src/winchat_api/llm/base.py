"""The provider-agnostic chat interface.

Every generation call in the request path goes through `ChatProvider`. Swapping Groq for
Anthropic or OpenAI means adding one class here and changing one environment variable — no call
site changes.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class Completion:
    """A finished generation, plus the accounting we need for cost + eval."""

    text: str
    model: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@runtime_checkable
class ChatProvider(Protocol):
    """A chat-completion backend.

    Implementations must be safe to share across requests (one client per process).
    """

    name: str
    model: str

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_object: bool = False,
    ) -> Completion:
        """Generate the full response.

        `json_object` asks the provider to constrain output to valid JSON. The eval judge
        depends on it: parsing a verdict out of prose is a source of flaky scores, and a grader
        that fails to parse silently biases the number it produces.
        """
        ...

    def stream(
        self,
        messages: Sequence[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Yield response text incrementally, for SSE streaming to the browser."""
        ...


class ProviderError(RuntimeError):
    """A provider call failed. Raised with a message safe to show in /readyz."""
