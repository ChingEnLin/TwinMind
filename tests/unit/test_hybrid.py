"""Hybrid retriever tests.

These verify the RRF math and the drop-in compatibility with the plain
Retriever interface. We use fake retriever objects (not real embeddings)
so we control the inputs and assert the fusion behavior precisely.
"""

from dataclasses import dataclass

from twin_mind.models.document import Chunk, Source
from twin_mind.retrieval.bm25 import BM25Retriever
from twin_mind.retrieval.hybrid import HybridRetriever
from twin_mind.vectorstore.base import ScoredChunk


def _chunk(id_: str, text: str = "") -> Chunk:
    return Chunk(id=id_, doc_id="d", source=Source(name="d"), text=text or id_)


@dataclass
class _FakeRetriever:
    """Returns a hand-picked ranked list, regardless of query."""

    store: object = None
    hits: list[ScoredChunk] = None

    def retrieve(self, query: str, k: int | None = None) -> list[ScoredChunk]:
        return list(self.hits or [])


def test_rrf_chunk_in_both_lists_beats_one_only():
    # Chunk "x" is #1 in vector and #2 in bm25 — should win.
    # Chunk "y" is #1 in bm25 only.
    # Chunk "z" is #2 in vector only.
    chunks = {cid: _chunk(cid) for cid in ("x", "y", "z")}
    vector = _FakeRetriever(
        store=None,
        hits=[ScoredChunk(chunks["x"], 0.9), ScoredChunk(chunks["z"], 0.8)],
    )
    bm25 = BM25Retriever([])  # we'll override retrieve below
    bm25.retrieve = lambda q, k: [  # type: ignore[method-assign]
        ScoredChunk(chunks["y"], 5.0),
        ScoredChunk(chunks["x"], 3.0),
    ]
    hr = HybridRetriever(vector, bm25, per_retriever_k=10, rrf_k=60, top_k=3)
    out = hr.retrieve("anything")
    ids = [s.chunk.id for s in out]
    assert ids[0] == "x", f"expected 'x' first (in both lists), got {ids}"
    # "y" and "z" each appear once; their RRF scores are equal -> order doesn't matter.
    assert set(ids[1:]) == {"y", "z"}


def test_rrf_respects_rank_not_raw_score():
    # If one retriever's raw scores were huge they'd swamp the other,
    # but RRF uses ranks so the huge magnitude is ignored.
    chunks = {cid: _chunk(cid) for cid in ("a", "b")}
    vector = _FakeRetriever(
        store=None,
        hits=[ScoredChunk(chunks["a"], 0.01)],  # rank 1, tiny score
    )
    bm25 = BM25Retriever([])
    bm25.retrieve = lambda q, k: [  # type: ignore[method-assign]
        ScoredChunk(chunks["b"], 1_000_000.0),  # rank 1, huge score
    ]
    hr = HybridRetriever(vector, bm25, per_retriever_k=10, rrf_k=60, top_k=2)
    out = hr.retrieve("anything")
    ids = [s.chunk.id for s in out]
    # Both are rank 1 in their respective list → equal RRF contribution.
    assert set(ids) == {"a", "b"}
    assert abs(out[0].score - out[1].score) < 1e-9


def test_hybrid_exposes_store_for_chat_route():
    # The chat route reads `retriever.store` for the meta event — hybrid must expose it.
    sentinel = object()
    vector = _FakeRetriever(store=sentinel, hits=[])
    bm25 = BM25Retriever([])
    hr = HybridRetriever(vector, bm25)
    assert hr.store is sentinel
