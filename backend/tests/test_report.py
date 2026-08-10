"""Wilson interval and the generated metrics table."""

import pytest

from winchat_api.evals.report import Proportion, build_markdown, wilson


def test_wilson_matches_published_values():
    """Checked against the standard worked example, 0.5 on n=100, to three decimals."""
    low, high = wilson(50, 100)
    assert round(low, 3) == 0.404
    assert round(high, 3) == 0.596


def test_wilson_does_not_collapse_at_one():
    """The reason Wald is not used. Wald gives 1.0 to 1.0 here and claims certainty."""
    low, high = wilson(26, 26)
    assert high == 1.0
    assert low < 0.90
    assert round(low, 3) == 0.871


def test_wilson_does_not_collapse_at_zero():
    low, high = wilson(0, 26)
    assert low == 0.0
    assert high > 0.10
    assert round(high, 3) == 0.129


def test_wilson_is_symmetric_between_the_edges():
    low_zero, high_zero = wilson(0, 26)
    low_all, high_all = wilson(26, 26)
    assert round(high_zero, 9) == round(1 - low_all, 9)


def test_wilson_narrows_as_n_grows():
    small = wilson(5, 10)
    large = wilson(500, 1000)
    assert (small[1] - small[0]) > (large[1] - large[0])


def test_wilson_returns_none_without_data():
    assert wilson(0, 0) is None


def test_wilson_rejects_impossible_counts():
    with pytest.raises(ValueError):
        wilson(5, 4)


def test_a_thin_category_says_so_rather_than_hiding_it():
    payload = {
        "model": "m",
        "judge_model": "j",
        "reranker": "r",
        "cases": [
            {"category": "adversarial", "deterministic": True},
            {"category": "adversarial", "deterministic": True},
        ],
    }
    table = build_markdown(payload)
    assert "n too small to be informative" in table


def test_categories_each_report_their_own_n():
    payload = {
        "model": "m",
        "judge_model": "j",
        "reranker": "r",
        "cases": [{"category": "answerable", "deterministic": True} for _ in range(9)]
        + [{"category": "refusal", "deterministic": False}],
    }
    table = build_markdown(payload)
    assert "answerable (9 cases)" in table
    assert "refusal (1 cases)" in table
    assert "Aggregate (10 cases)" in table


def test_a_metric_nobody_scored_is_omitted_not_shown_as_zero():
    """A metric with no judged cases must not appear as 0%, which reads as total failure."""
    payload = {
        "model": "m",
        "judge_model": "j",
        "reranker": "r",
        "cases": [{"category": "answerable", "deterministic": True, "faithful": None}],
    }
    assert "faithfulness" not in build_markdown(payload)


def test_proportion_reports_its_own_interval():
    p = Proportion("x", 24, 26)
    assert p.point == pytest.approx(24 / 26)
    low, high = p.interval
    assert low < p.point < high
