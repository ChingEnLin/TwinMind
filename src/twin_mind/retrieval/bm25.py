"""BM25 keyword retriever.

A classic sparse retriever that complements the dense vector retriever:
- Vector retrieval shines on paraphrase ("speed up the workflow" → "reduced
  processing time").
- BM25 shines on exact-token matches (repo names, library names, jargon)
  that embedders soften because they were trained to generalize across
  vocabulary.

We build the index in-process from the same chunks the vector store holds.
Re-built at server boot from ``store.all_chunks()`` — for portfolio-scale
corpora (≤ low thousands of chunks) this takes milliseconds.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from rank_bm25 import BM25Okapi

from twin_mind.models.document import Chunk
from twin_mind.vectorstore.base import ScoredChunk

# A short stopword list. Real BM25 implementations sometimes use larger ones,
# but for short technical content this is plenty and avoids dragging in NLTK.
_STOPWORDS = frozenset(
    """
    a an the and or but if then else of for to from in on at by with as is are was were be been
    being do does did have has had this that these those it its i you he she we they what which
    who whom how why when where there here not no nor so too very can will just don should now
    """.split()
)

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on word chars, drop stopwords."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t and t not in _STOPWORDS]


class BM25Retriever:
    name = "bm25"

    def __init__(self, chunks: Iterable[Chunk]) -> None:
        self._chunks: list[Chunk] = list(chunks)
        self._tokenized: list[list[str]] = [_tokenize(c.text) for c in self._chunks]
        # ``BM25Okapi`` requires at least one document with at least one token.
        self._bm25: BM25Okapi | None = None
        if self._chunks and any(self._tokenized):
            # Replace any empty token lists with a single placeholder so BM25
            # doesn't divide by zero when computing IDF for that chunk.
            normalized = [toks or ["__empty__"] for toks in self._tokenized]
            self._bm25 = BM25Okapi(normalized)

    def retrieve(self, query: str, k: int) -> list[ScoredChunk]:
        if self._bm25 is None or not self._chunks:
            return []
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        scores = self._bm25.get_scores(q_tokens)
        # Pair, sort desc, slice top-k.
        ranked = sorted(
            zip(self._chunks, scores, strict=True), key=lambda p: p[1], reverse=True
        )
        return [ScoredChunk(c, float(s)) for c, s in ranked[:k] if s > 0]

    def __len__(self) -> int:
        return len(self._chunks)
