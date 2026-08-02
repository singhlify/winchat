"""Chunking tests. Pure functions, no network, no database."""

from winchat_api.ingestion.chunking import (
    DEFAULT_MAX_CHARS,
    DEFAULT_OVERLAP_CHARS,
    chunk_answer,
)


def _chunk(text: str, **kwargs):
    return chunk_answer(a_id="1", question="What is the deadline?", answer_text=text, **kwargs)


def test_short_answer_stays_whole():
    """85% of this corpus is one chunk; splitting an intact FAQ answer would lose context."""
    chunks = _chunk("Applications close on March 1.")

    assert len(chunks) == 1
    assert chunks[0].content == "Applications close on March 1."
    assert chunks[0].chunk_index == 0


def test_every_chunk_carries_its_question():
    """Contextual retrieval: chunk 3 of a long answer must still say what it answers."""
    chunks = _chunk("\n\n".join(f"Paragraph {i}. " + "word " * 120 for i in range(6)))

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.context_text.startswith("What is the deadline?")
        assert chunk.content in chunk.context_text


def test_chunks_respect_the_documented_size_bound():
    chunks = _chunk("\n\n".join(f"Paragraph {i}. " + "word " * 120 for i in range(8)))

    for chunk in chunks:
        assert len(chunk.content) <= DEFAULT_MAX_CHARS + DEFAULT_OVERLAP_CHARS


def test_chunks_are_indexed_in_order():
    chunks = _chunk("\n\n".join(f"Paragraph {i}. " + "word " * 120 for i in range(6)))

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_consecutive_chunks_overlap():
    """A fact on the seam must be retrievable from either side."""
    chunks = _chunk("\n\n".join(f"Paragraph {i}. " + "word " * 120 for i in range(4)))

    assert len(chunks) > 1
    tail = chunks[0].content[-DEFAULT_OVERLAP_CHARS:]
    assert any(word and word in chunks[1].content for word in tail.split()[:3])


def test_a_single_oversized_sentence_is_hard_cut():
    """An unpunctuated wall of text must not become one chunk the model would truncate."""
    chunks = _chunk("word " * 2000)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.content) <= DEFAULT_MAX_CHARS + DEFAULT_OVERLAP_CHARS


def test_empty_answer_produces_no_chunks():
    assert _chunk("   \n\n  ") == []


def test_splitting_prefers_paragraph_boundaries():
    paragraphs = [f"Paragraph {i}. " + "word " * 100 for i in range(4)]
    chunks = _chunk("\n\n".join(paragraphs))

    # No chunk should begin mid-word.
    for chunk in chunks:
        assert not chunk.content.startswith(" ")
