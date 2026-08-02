"""Tier 2: LLM-as-judge over faithfulness and correctness.

Two separate scores, because they fail independently. An answer can be perfectly faithful
to its sources and still not address the question, and a "correct-sounding" answer can be
faithful to nothing. Collapsing them into one number hides which half broke.

**Faithfulness** is judged against the retrieved context ONLY — the judge is not allowed
to use its own knowledge, because the question being asked is "did the model make this up
given what it was shown", not "is this true in the world".

**The judge is deliberately a different model family from the generator.** The app
generates with Llama and judges with GPT-OSS. Models systematically prefer their own
outputs, so a Llama judge grading Llama answers inflates the score in a way no threshold
can correct for. Cross-family judging does not eliminate the bias, but it stops it
compounding.

The judge model is pinned in config and reported with every score. "92% faithful" is
meaningless without naming the grader.
"""

import json
import logging
from dataclasses import dataclass

from winchat_api.llm.base import ChatProvider, Message

logger = logging.getLogger(__name__)

FAITHFULNESS_PROMPT = """You grade whether an ANSWER is fully supported by its SOURCES.

Judge ONLY what the sources say. Do not use outside knowledge. An answer is unfaithful if \
it states any fact, number, date, name, or contact detail that the sources do not contain, \
even if that fact is true in the real world.

Saying "the sources do not cover this" is faithful. Declining to answer is faithful.

Reply with JSON only:
{"faithful": true|false, "unsupported_claims": ["..."], "reason": "one sentence"}"""

CORRECTNESS_PROMPT = """You grade whether an ANSWER actually addresses the QUESTION.

An answer is correct if a person asking that question would get what they needed. An \
honest, specific "I don't know, contact X" is CORRECT when the sources genuinely lack the \
answer. A fluent answer to a different question is INCORRECT.

Reply with JSON only:
{"correct": true|false, "reason": "one sentence"}"""


@dataclass
class Verdict:
    faithful: bool | None = None
    correct: bool | None = None
    unsupported_claims: list[str] | None = None
    faithfulness_reason: str = ""
    correctness_reason: str = ""
    error: str | None = None


async def _judge_json(judge: ChatProvider, system: str, user: str) -> dict:
    completion = await judge.complete(
        [Message(role="system", content=system), Message(role="user", content=user)],
        temperature=0.0,
        max_tokens=500,
        json_object=True,
    )
    return json.loads(completion.text)


async def judge_answer(judge: ChatProvider, *, question: str, answer: str, context: str) -> Verdict:
    """Score one answer. A judge failure is recorded, never silently counted as a pass."""
    verdict = Verdict()

    try:
        faithfulness = await _judge_json(
            judge,
            FAITHFULNESS_PROMPT,
            f"SOURCES:\n{context or '(no sources were retrieved)'}\n\nANSWER:\n{answer}",
        )
        verdict.faithful = bool(faithfulness.get("faithful"))
        verdict.unsupported_claims = faithfulness.get("unsupported_claims") or []
        verdict.faithfulness_reason = str(faithfulness.get("reason", ""))[:300]
    except Exception as exc:
        verdict.error = f"faithfulness judge failed: {exc}"[:200]
        logger.warning(verdict.error)

    try:
        correctness = await _judge_json(
            judge,
            CORRECTNESS_PROMPT,
            f"QUESTION:\n{question}\n\nANSWER:\n{answer}",
        )
        verdict.correct = bool(correctness.get("correct"))
        verdict.correctness_reason = str(correctness.get("reason", ""))[:300]
    except Exception as exc:
        verdict.error = f"{verdict.error or ''} correctness judge failed: {exc}"[:200]
        logger.warning("correctness judge failed: %s", exc)

    return verdict
