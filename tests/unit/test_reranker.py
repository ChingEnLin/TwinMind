"""Unit tests for the reranker layer.

Covers:
- IdentityReranker pass-through behavior
- RerankedRetriever's two-stage flow (base fetches candidate_k, reranker trims to k)
- ClaudeReranker output parsing (the only branch that needs unit-test coverage
  without hitting the API; the cross-encoder is exercised via integration eval)
"""

from twin_mind.models.document import Chunk, Source
from twin_mind.retrieval.reranked import RerankedRetriever
from twin_mind.retrieval.reranker.adapters.claude import _parse_ranking
from twin_mind.retrieval.reranker.adapters.identity import IdentityReranker
from twin_mind.vectorstore.base import ScoredChunk


def _sc(chunk_id: str) -> ScoredChunk:
    return ScoredChunk(
        chunk=Chunk(id=chunk_id, doc_id="d", source=Source(name=f"{chunk_id}.md"), text=chunk_id),
        score=1.0,
    )


class _FakeBase:
    """Stand-in retriever that records the k it was called with."""

    def __init__(self, hits: list[ScoredChunk]) -> None:
        self._hits = hits
        self.last_k: int | None = None
        self.store = None

    def retrieve(self, query: str, k: int | None = None) -> list[ScoredChunk]:
        self.last_k = k
        return self._hits[:k] if k is not None else self._hits


# ----- IdentityReranker -----------------------------------------------------


def test_identity_reranker_returns_first_k():
    r = IdentityReranker()
    candidates = [_sc("a"), _sc("b"), _sc("c"), _sc("d")]
    assert [s.chunk.id for s in r.rerank("q", candidates, 2)] == ["a", "b"]


def test_identity_reranker_handles_fewer_candidates_than_k():
    r = IdentityReranker()
    candidates = [_sc("a")]
    assert [s.chunk.id for s in r.rerank("q", candidates, 5)] == ["a"]


# ----- RerankedRetriever ----------------------------------------------------


def test_reranked_retriever_fetches_candidate_k_not_top_k():
    base = _FakeBase([_sc(c) for c in "abcdefghij"])
    reranker = IdentityReranker()
    wrapped = RerankedRetriever(base, reranker, candidate_k=8, top_k=3)

    out = wrapped.retrieve("q")
    assert base.last_k == 8, "base should be called with candidate_k, not top_k"
    assert len(out) == 3


def test_reranked_retriever_respects_caller_k_override():
    base = _FakeBase([_sc(c) for c in "abcde"])
    wrapped = RerankedRetriever(base, IdentityReranker(), candidate_k=5, top_k=2)
    out = wrapped.retrieve("q", k=4)
    assert len(out) == 4


def test_reranked_retriever_empty_candidates_short_circuits():
    base = _FakeBase([])
    wrapped = RerankedRetriever(base, IdentityReranker(), candidate_k=5, top_k=2)
    assert wrapped.retrieve("q") == []


# ----- Claude listwise parse ------------------------------------------------


def test_claude_parse_valid_json_array():
    assert _parse_ranking("[2, 0, 1]", 3) == [2, 0, 1]


def test_claude_parse_strips_markdown_fences():
    assert _parse_ranking("```json\n[1, 0]\n```", 2) == [1, 0]


def test_claude_parse_extracts_array_from_surrounding_prose():
    assert _parse_ranking("Sure! Here is the ranking: [0, 2, 1] done.", 3) == [0, 2, 1]


def test_claude_parse_fills_missing_indices_in_original_order():
    # Model omitted index 2 — we must still return all 3 positions.
    out = _parse_ranking("[1, 0]", 3)
    assert out == [1, 0, 2]


def test_claude_parse_drops_out_of_range_and_duplicates():
    out = _parse_ranking("[0, 0, 5, 1, -1]", 3)
    assert out == [0, 1, 2]


def test_claude_parse_returns_none_on_garbage():
    assert _parse_ranking("the model refused to comply", 3) is None
