"""Hybrid retriever: fuses dense (vector) and sparse (BM25) retrieval.

Uses **Reciprocal Rank Fusion (RRF)** — for each chunk, the fused score is
the sum over each retriever of ``1 / (RRF_K + rank_in_that_retriever)``.

Why RRF:
- It only needs ranks, not raw scores. Vector cosine and BM25 produce
  scores on incompatible scales; rank-based fusion sidesteps normalization.
- A chunk that appears in both lists gets a boost (sum of two reciprocals).
- A chunk only in one list still contributes its single reciprocal.
- No tuning required beyond the smoothing constant K (default 60, lifted
  from the original 2009 RRF paper — works well in practice).

The fused retriever exposes the same ``retrieve(query, k) -> list[ScoredChunk]``
interface as the plain vector ``Retriever``, so callers don't change.
"""

from __future__ import annotations

from twin_mind.config import settings
from twin_mind.models.document import Chunk
from twin_mind.retrieval.bm25 import BM25Retriever
from twin_mind.retrieval.retriever import Retriever
from twin_mind.vectorstore.base import ScoredChunk


class HybridRetriever:
    name = "hybrid"

    def __init__(
        self,
        vector: Retriever,
        bm25: BM25Retriever,
        per_retriever_k: int | None = None,
        rrf_k: int | None = None,
        top_k: int | None = None,
    ) -> None:
        self.vector = vector
        self.bm25 = bm25
        self.per_retriever_k = per_retriever_k or settings.HYBRID_PER_RETRIEVER_K
        self.rrf_k = rrf_k if rrf_k is not None else settings.RRF_K
        self.top_k = top_k or settings.TOP_K
        # For the chat route's `meta` event: expose a `.store` shim so retriever.store works.
        self.store = vector.store

    def retrieve(self, query: str, k: int | None = None) -> list[ScoredChunk]:
        out_k = k or self.top_k

        vec_hits = self.vector.retrieve(query, k=self.per_retriever_k)
        bm25_hits = self.bm25.retrieve(query, k=self.per_retriever_k)

        # Build a lookup so we keep one Chunk reference per id.
        by_id: dict[str, Chunk] = {}
        fused: dict[str, float] = {}

        for rank, sc in enumerate(vec_hits):
            cid = sc.chunk.id
            by_id.setdefault(cid, sc.chunk)
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (self.rrf_k + rank + 1)

        for rank, sc in enumerate(bm25_hits):
            cid = sc.chunk.id
            by_id.setdefault(cid, sc.chunk)
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (self.rrf_k + rank + 1)

        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
        return [ScoredChunk(by_id[cid], score) for cid, score in ranked[:out_k]]
