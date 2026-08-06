"""Corpus-loading and change-detection tests. No network, no database."""

import json

import pytest

from winchat_api.ingestion.corpus import Answer, CorpusError, load_answers, normalize_whitespace
from winchat_api.ingestion.pipeline import _needs_work

RECORD = {
    "a_id": "246",
    "question": "How do I activate my UWin Account?",
    "answer_text": "Go to the activation page and enter your student number.",
    "url": "https://ask.uwindsor.ca/app/answers/detail/a_id/246",
    "lastmod": "2025-11-21T10:00:03-05:00",
    "fetched_at": "2026-08-02T10:37:52.821684+00:00",
}


def _write_corpus(tmp_path, records):
    path = tmp_path / "answers.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    return path


def test_loads_and_parses_a_record(tmp_path):
    answers = load_answers(_write_corpus(tmp_path, [RECORD]))

    assert len(answers) == 1
    answer = answers[0]
    assert answer.a_id == "246"
    assert answer.lastmod is not None and answer.lastmod.year == 2025
    assert answer.fetched_at is not None


def test_numeric_a_id_becomes_a_string(tmp_path):
    """The scraper may emit ints; the primary key must stay one type."""
    answers = load_answers(_write_corpus(tmp_path, [{**RECORD, "a_id": 246}]))

    assert answers[0].a_id == "246"


def test_missing_corpus_names_the_fix(tmp_path):
    with pytest.raises(CorpusError, match="scrape_ask_uwindsor"):
        load_answers(tmp_path / "nope.jsonl")


def test_a_record_missing_a_field_is_an_error_not_a_silent_skip(tmp_path):
    broken = {**RECORD, "answer_text": ""}

    with pytest.raises(CorpusError, match="answer_text"):
        load_answers(_write_corpus(tmp_path, [broken]))


def test_duplicate_ids_are_rejected(tmp_path):
    with pytest.raises(CorpusError, match="duplicate"):
        load_answers(_write_corpus(tmp_path, [RECORD, RECORD]))


def test_malformed_json_reports_the_line_number(tmp_path):
    path = tmp_path / "answers.jsonl"
    path.write_text(json.dumps(RECORD) + "\n{not json\n")

    with pytest.raises(CorpusError, match=":2"):
        load_answers(path)


def test_normalize_whitespace_collapses_scraped_padding():
    assert normalize_whitespace("a  b \n\n\n\n c ") == "a b\n\nc"


def _answer(question="Q", answer_text="A") -> Answer:
    return Answer(
        a_id="1", question=question, answer_text=answer_text, url="u", lastmod=None, fetched_at=None
    )


def test_content_hash_ignores_metadata_but_tracks_text():
    """A touched lastmod must not cost an embedding call; a real edit must."""
    assert _answer().content_hash == _answer().content_hash
    assert _answer(answer_text="A").content_hash != _answer(answer_text="B").content_hash


def test_unseen_answer_needs_work():
    assert _needs_work(_answer(), None, "nomic-embed-text") is True


def test_unchanged_answer_is_skipped():
    answer = _answer()
    state = (answer.content_hash, "nomic-embed-text")
    assert _needs_work(answer, state, "nomic-embed-text") is False


def test_edited_answer_is_re_embedded():
    answer = _answer(answer_text="new text")
    assert _needs_work(answer, ("some-old-hash", "nomic-embed-text"), "nomic-embed-text") is True


def test_changing_the_embedding_model_forces_a_re_embed():
    """Vectors from two models are not comparable; mixing them degrades retrieval silently."""
    answer = _answer()
    assert _needs_work(answer, (answer.content_hash, "bge-large"), "nomic-embed-text") is True


def test_answer_row_without_chunks_is_retried():
    """A run that died between writing the answer and its chunks must self-heal."""
    answer = _answer()
    assert _needs_work(answer, (answer.content_hash, None), "nomic-embed-text") is True


# --- corpus provenance --------------------------------------------------------------


def _corpus(tmp_path, url):
    import json

    p = tmp_path / "answers.jsonl"
    p.write_text(
        json.dumps({"a_id": "1", "question": "Q?", "answer_text": "A.", "url": url}) + "\n",
        encoding="utf-8",
    )
    return p


def test_the_real_source_host_is_accepted(tmp_path):
    from winchat_api.ingestion.corpus import load_answers

    answers = load_answers(_corpus(tmp_path, "https://ask.uwindsor.ca/app/answers/detail/a_id/1"))

    assert len(answers) == 1


def test_a_foreign_host_fails_the_ingest(tmp_path):
    """Every citation is a link the UI invites the user to trust. A URL from a file on disk
    must not inherit that trust unchecked."""
    from winchat_api.ingestion.corpus import CorpusError, load_answers

    with pytest.raises(CorpusError, match="not an allowed source"):
        load_answers(_corpus(tmp_path, "https://evil.example/phish"))


def test_a_suffix_lookalike_host_is_rejected(tmp_path):
    """`endswith('uwindsor.ca')` would accept this. Exact host match is why it does not."""
    from winchat_api.ingestion.corpus import CorpusError, load_answers

    with pytest.raises(CorpusError, match="not an allowed source"):
        load_answers(_corpus(tmp_path, "https://ask.uwindsor.ca.attacker.example/x"))


def test_a_non_http_scheme_is_rejected(tmp_path):
    from winchat_api.ingestion.corpus import CorpusError, load_answers

    with pytest.raises(CorpusError, match="not http"):
        load_answers(_corpus(tmp_path, "javascript:alert(1)"))
