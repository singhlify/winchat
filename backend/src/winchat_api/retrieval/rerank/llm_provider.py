"""Reranking with the language model we already have.

A dedicated cross-encoder (Cohere Rerank) is the better tool, but it needs a vendor key.
This implements the same `Reranker` interface using the configured LLM, so the pipeline
gets its precision stage today and swapping in Cohere later is a config change — which is
the entire point of having the interface.

It is a *listwise* reranker: every candidate is shown at once and the model returns an
ordering, rather than scoring each passage independently. One call instead of N, and the
model can compare candidates against each other, which is exactly the judgement that
separates "the article about UwinCARD fees, which mentions office hours" from "the article
about academic advising hours".

Why this stage is needed at all, measured on this corpus: recall inside the 40-candidate
pool is 100% while recall at the top 6 is 83%. The right passage is always retrieved and
sometimes ranked too low — the textbook case for a reranker, and the opposite of the case
where one cannot help.

Deliberately uses a small fast model. Ordering candidates is a much easier task than
answering from them, and putting the slow model here would double the latency of every
question.
"""

import json
import logging
from collections.abc import Sequence

from winchat_api.llm.base import ChatProvider, Message, ProviderError
from winchat_api.retrieval.models import RetrievedChunk
from winchat_api.retrieval.rerank.base import Reranker, RerankError

logger = logging.getLogger(__name__)

# These two trade against each other and the trade is NOT settled. Measured over the 18
# retrieval-scored golden cases (baseline, no reranker: recall 83.3%, MRR 0.409):
#
#   20 candidates / 240 chars -> recall 88.9%, MRR 0.833   <- current
#   12 candidates / 400 chars -> recall 66.7%, MRR 0.528
#
# Fewer candidates with longer snippets was much worse: the small model over-filters, and
# dropping to 12 also cuts off correct passages sitting at fused rank 13-20. Longer
# snippets are not free either — 20x480 chars is ~2.4k tokens per question against a 6k
# tokens-per-MINUTE free-tier ceiling, at which point nearly every rerank is rate-limited
# into the RRF fallback and any measurement is really measuring RRF.
#
# Known limitation of the current setting: the answer to "UwinCARD Office hours" lives in
# an article titled "Is there a fee for the UwinCARD?" with the times at character 243, so
# a 240-char snippet stops three characters before the evidence and the reranker cannot
# see it. It ranks better on average and worse on that case. Resolving this properly needs
# a real cross-encoder, which reads whole passages and does not pay per token.
MAX_CANDIDATES = 20
SNIPPET_CHARS = 240

RERANK_PROMPT = """You rank search results for a University of Windsor FAQ assistant.

Given a QUESTION and numbered CANDIDATE passages, return the numbers of the passages that \
actually help answer the question, best first.

Judge whether a passage contains the specific information asked for — not merely whether \
it is on a related topic. A passage about a different service, office or programme that \
happens to share vocabulary is NOT relevant. A passage whose main subject is something \
else but which explicitly states the requested detail IS relevant.

Include only genuinely useful passages. Returning fewer is better than padding the list.

Reply with JSON only: {"ranked": [3, 1, 7]}"""


class LLMReranker(Reranker):
    name = "llm"

    def __init__(self, *, llm: ChatProvider) -> None:
        self._llm = llm
        self.model = llm.model

    async def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], *, top_n: int
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []

        candidates = list(chunks[:MAX_CANDIDATES])
        listing = "\n".join(
            f"{index}. {chunk.question} — {chunk.content[:SNIPPET_CHARS]}"
            for index, chunk in enumerate(candidates, start=1)
        )

        try:
            completion = await self._llm.complete(
                [
                    Message(role="system", content=RERANK_PROMPT),
                    Message(
                        role="user",
                        content=f"QUESTION: {query}\n\nCANDIDATES:\n{listing}",
                    ),
                ],
                temperature=0.0,
                max_tokens=200,
                json_object=True,
            )
            ranked = json.loads(completion.text).get("ranked", [])
        except ProviderError as exc:
            raise RerankError(f"llm rerank: {exc}") from exc
        except (json.JSONDecodeError, AttributeError) as exc:
            raise RerankError(f"llm rerank: unparseable ordering ({exc})") from exc

        ordered: list[RetrievedChunk] = []
        seen: set[int] = set()
        for position, raw in enumerate(ranked):
            # The model returns 1-based positions; anything out of range is ignored rather
            # than trusted, because a hallucinated index must not raise or wrap around.
            try:
                index = int(raw) - 1
            except (TypeError, ValueError):
                continue
            if index < 0 or index >= len(candidates) or index in seen:
                continue
            seen.add(index)
            chunk = candidates[index]
            # A descending score derived from position, so downstream code and the refusal
            # gate see a comparable number rather than a bare ordering.
            chunk.scores["rerank"] = round(1.0 - position / max(len(candidates), 1), 4)
            ordered.append(chunk)
            if len(ordered) >= top_n:
                break

        if not ordered:
            # The model judged nothing relevant. That is a legitimate verdict and the
            # refusal gate should see it, so fused order is NOT silently substituted.
            logger.info("llm rerank kept no candidates for %r", query[:80])

        return ordered
