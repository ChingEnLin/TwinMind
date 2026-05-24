"""Reranked retriever: wraps any retriever, reorders its top candidates.

Two-stage retrieval:
1. base retriever (vector / bm25 / hybrid) fetches ``candidate_k`` chunks
   using cheap signals (cosine, BM25, RRF) — high recall, mediocre precision.
2. reranker scores each (query, chunk) pair with a more expensive but
   accurate signal (cross-encoder cross-attention, or LLM-as-judge), then
   returns the top ``k``.

This is the standard "retrieve-then-rerank" pattern. Decoupling it from
HybridRetriever keeps each layer single-purpose: fusion is fusion,
reranking is reranking.
"""

from __future__ import annotations

from twin_mind.config import settings
from twin_mind.retrieval.reranker.base import Reranker
from twin_mind.vectorstore.base import ScoredChunk


class RerankedRetriever:
    name = "reranked"

    def __init__(
        self,
        base,
        reranker: Reranker,
        candidate_k: int | None = None,
        top_k: int | None = None,
    ) -> None:
        self.base = base
        self.reranker = reranker
        self.candidate_k = candidate_k or settings.RERANKER_CANDIDATE_K
        self.top_k = top_k or settings.TOP_K
        # Expose .store so callers that peek at retriever.store (e.g. chat meta event) keep working.
        self.store = getattr(base, "store", None)

    def retrieve(self, query: str, k: int | None = None) -> list[ScoredChunk]:
        out_k = k or self.top_k
        candidates = self.base.retrieve(query, k=self.candidate_k)
        if not candidates:
            return []
        return self.reranker.rerank(query, candidates, out_k)
