"""Judge plumbing tests. The verdict content needs a model; the plumbing must not."""

import pytest

from winchat_api.evals.judge import CORRECTNESS_PROMPT, FAITHFULNESS_PROMPT, judge_answer
from winchat_api.llm.base import Completion


class _StubJudge:
    """Returns canned JSON and records what it was asked."""

    name = "stub"
    model = "stub"

    def __init__(self, *payloads: str):
        self.payloads = list(payloads)
        self.prompts: list[str] = []

    async def complete(self, messages, **kwargs):
        self.prompts.append(messages[-1].content)
        assert kwargs.get("json_object") is True, "the judge must request JSON mode"
        return Completion(text=self.payloads.pop(0), model="stub", provider="stub")


async def test_a_clean_verdict_is_parsed():
    judge = _StubJudge('{"faithful": true, "reason": "ok"}', '{"correct": true, "reason": "ok"}')

    verdict = await judge_answer(judge, question="q", answer="a", context="c")

    assert verdict.faithful is True
    assert verdict.correct is True
    assert verdict.error is None


async def test_both_judges_see_the_sources():
    """Without sources the correctness judge cannot tell a justified refusal from a lazy one."""
    judge = _StubJudge('{"faithful": true}', '{"correct": true}')

    await judge_answer(judge, question="q", answer="a", context="THE-SOURCES")

    assert all("THE-SOURCES" in prompt for prompt in judge.prompts)


async def test_unparseable_output_is_recorded_not_counted_as_a_pass():
    """A silent judge failure biases every score it is averaged into."""
    judge = _StubJudge("not json at all", '{"correct": true}')

    verdict = await judge_answer(judge, question="q", answer="a", context="c")

    assert verdict.faithful is None
    assert verdict.error is not None


def test_the_prompts_state_that_declining_is_correct_behaviour():
    """Regression guard: the first version graded the system as a general assistant and
    marked every correct refusal, and a resisted prompt injection, as a failure."""
    assert "FAITHFUL" in FAITHFULNESS_PROMPT
    assert "declines" in CORRECTNESS_PROMPT
    assert "override" in CORRECTNESS_PROMPT


@pytest.mark.parametrize("prompt", [FAITHFULNESS_PROMPT, CORRECTNESS_PROMPT])
def test_every_prompt_describes_the_system_under_test(prompt):
    assert "FAQ assistant" in prompt
