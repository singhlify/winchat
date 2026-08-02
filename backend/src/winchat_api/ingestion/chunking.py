"""Splitting answers into retrievable chunks.

Sized for this corpus, not from a tutorial default. Measured over all 556 answers:
median 621 characters, 90th percentile 1,900, max 4,263. At a 1,600-character target
roughly nine in ten answers stay whole — which is what we want, because an intact FAQ
answer is already the ideal retrieval unit and splitting it would strand its conclusion in
a chunk that no longer mentions the topic. Only the long tail gets split.

Splits prefer paragraph boundaries, then sentences, and only cut mid-sentence when a
single sentence is itself oversized. Overlap carries the tail of one chunk into the next so
a fact spanning the seam is still retrievable from either side.

`max_chars` bounds the text a chunk is *built* from; the carried-over overlap is added on
top, so the true upper bound is `max_chars + overlap_chars`. Measured over this corpus:
665 chunks from 556 answers, 85% single-chunk, largest 1,749 characters.

Every chunk is paired with its parent question before embedding (see `context_text`).
That is contextual retrieval: chunk 3 of a long answer contains no clue what question it
answers, and the question is the highest-signal context available for free.
"""

import re
from dataclasses import dataclass

# ~1,600 characters ≈ 400 tokens. Research puts factoid Q&A retrieval in the 256-512 token
# band; this corpus is factoid FAQ. nomic-embed's 8k window is not the binding constraint —
# retrieval precision is.
DEFAULT_MAX_CHARS = 1600
DEFAULT_OVERLAP_CHARS = 200

_PARAGRAPH_BREAK = re.compile(r"\n{2,}")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class Chunk:
    a_id: str
    chunk_index: int
    content: str
    context_text: str

    @property
    def token_estimate(self) -> int:
        """Rough count. Exact tokenization would tie us to one model's tokenizer."""
        return max(1, len(self.context_text) // 4)


def build_context_text(question: str, content: str) -> str:
    """What actually gets embedded and full-text indexed."""
    return f"{question}\n\n{content}"


def chunk_answer(
    *,
    a_id: str,
    question: str,
    answer_text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    pieces = _split_text(answer_text, max_chars=max_chars, overlap_chars=overlap_chars)
    return [
        Chunk(
            a_id=a_id,
            chunk_index=index,
            content=piece,
            context_text=build_context_text(question, piece),
        )
        for index, piece in enumerate(pieces)
    ]


def _split_text(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    units = _atomic_units(text, max_chars=max_chars)

    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            tail = _overlap_tail(current, overlap_chars)
            current = f"{tail}\n\n{unit}" if tail else unit
        else:
            current = unit

    if current:
        chunks.append(current)
    return chunks


def _atomic_units(text: str, *, max_chars: int) -> list[str]:
    """Break into the largest pieces that still fit, preferring natural boundaries."""
    units: list[str] = []
    for paragraph in _PARAGRAPH_BREAK.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= max_chars:
            units.append(paragraph)
            continue

        for sentence in _SENTENCE_END.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) <= max_chars:
                units.append(sentence)
            else:
                # A single oversized sentence (a long unpunctuated list, usually). Hard-cut
                # it rather than emit a chunk the embedding model would truncate.
                units.extend(
                    sentence[start : start + max_chars]
                    for start in range(0, len(sentence), max_chars)
                )
    return units


def _overlap_tail(chunk: str, overlap_chars: int) -> str:
    """The trailing slice of a chunk, snapped forward to a word boundary."""
    if overlap_chars <= 0 or len(chunk) <= overlap_chars:
        return ""
    tail = chunk[-overlap_chars:]
    space = tail.find(" ")
    return tail[space + 1 :].strip() if space != -1 else tail.strip()
