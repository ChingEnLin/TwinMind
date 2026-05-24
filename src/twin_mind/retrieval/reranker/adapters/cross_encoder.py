"""Cross-encoder reranker via sentence-transformers.

A cross-encoder takes (query, passage) as a *single* concatenated input and
produces a relevance score from a model that has attended over both pieces
of text jointly. This is more accurate than the bi-encoder vector retrieval
which embeds query and passage independently and only sees them via cosine —
but it's also too slow to run on the whole corpus. So we use it as a second
stage on the top-K candidates.

Default model: ``BAAI/bge-reranker-base`` (~280M params). Outputs raw logits
that are monotonic with relevance; no sigmoid needed for ordering.
"""

from __future__ import annotations

from threading import Lock

from twin_mind.config import settings
from twin_mind.vectorstore.base import ScoredChunk


class CrossEncoderReranker:
    name = "cross_encoder"

    def __init__(self, model_name: str | None = None) -> None:
        from sentence_transformers import CrossEncoder

        self.model_name = model_name or settings.CROSS_ENCODER_MODEL
        self._model = CrossEncoder(self.model_name)
        self._lock = Lock()

    def rerank(self, query: str, candidates: list[ScoredChunk], k: int) -> list[ScoredChunk]:
        if not candidates:
            return []
        pairs = [(query, sc.chunk.text) for sc in candidates]
        with self._lock:
            scores = self._model.predict(pairs, show_progress_bar=False)
        ranked = sorted(zip(candidates, scores, strict=True), key=lambda p: p[1], reverse=True)
        return [ScoredChunk(sc.chunk, float(score)) for sc, score in ranked[:k]]
