"""Pure-math tests for the cheap eval metrics."""

from twin_mind.eval.metrics import citation_precision, refusal_correct, retrieval_recall
from twin_mind.eval.runner import EvalCase, EvalResult
from twin_mind.models.document import Chunk, Source
from twin_mind.vectorstore.base import ScoredChunk


def _sc(chunk_id: str, source_name: str) -> ScoredChunk:
    return ScoredChunk(
        chunk=Chunk(id=chunk_id, doc_id="d", source=Source(name=source_name), text="x"),
        score=1.0,
    )


def _result(
    *,
    expected_sources: list[str],
    retrieved: list[ScoredChunk],
    citations: list[str],
    refused: bool = False,
    should_refuse: bool = False,
    refusal_reason: str | None = None,
    expected_refusal_reason: str | None = None,
) -> EvalResult:
    case = EvalCase(
        id="t",
        question="q",
        expected_sources=expected_sources,
        should_refuse=should_refuse,
        expected_refusal_reason=expected_refusal_reason,
    )
    return EvalResult(
        case=case,
        answer="a",
        refused=refused,
        refusal_reason=refusal_reason,
        citations=citations,
        retrieved=retrieved,
    )


class TestRetrievalRecall:
    def test_full_hit(self):
        r = _result(
            expected_sources=["a.md"],
            retrieved=[_sc("a.md#0", "a.md"), _sc("b.md#0", "b.md")],
            citations=[],
        )
        assert retrieval_recall(r) == 1.0

    def test_miss(self):
        r = _result(
            expected_sources=["a.md"],
            retrieved=[_sc("b.md#0", "b.md")],
            citations=[],
        )
        assert retrieval_recall(r) == 0.0

    def test_partial(self):
        r = _result(
            expected_sources=["a.md", "b.md"],
            retrieved=[_sc("a.md#0", "a.md")],
            citations=[],
        )
        assert retrieval_recall(r) == 0.5

    def test_no_expected_returns_none(self):
        r = _result(expected_sources=[], retrieved=[_sc("x.md#0", "x.md")], citations=[])
        assert retrieval_recall(r) is None


class TestCitationPrecision:
    def test_all_correct(self):
        r = _result(
            expected_sources=["a.md"],
            retrieved=[_sc("a.md#0", "a.md"), _sc("b.md#0", "b.md")],
            citations=["a.md#0"],
        )
        assert citation_precision(r) == 1.0

    def test_half_wrong(self):
        r = _result(
            expected_sources=["a.md"],
            retrieved=[_sc("a.md#0", "a.md"), _sc("b.md#0", "b.md")],
            citations=["a.md#0", "b.md#0"],
        )
        assert citation_precision(r) == 0.5

    def test_refused_returns_none(self):
        r = _result(expected_sources=["a.md"], retrieved=[], citations=[], refused=True)
        assert citation_precision(r) is None

    def test_no_citations_zero(self):
        r = _result(expected_sources=["a.md"], retrieved=[_sc("a.md#0", "a.md")], citations=[])
        assert citation_precision(r) == 0.0


class TestRefusalCorrect:
    def test_should_refuse_did(self):
        r = _result(
            expected_sources=[],
            retrieved=[],
            citations=[],
            should_refuse=True,
            refused=True,
            refusal_reason="out_of_corpus",
        )
        assert refusal_correct(r) is True

    def test_should_refuse_didnt(self):
        r = _result(
            expected_sources=[], retrieved=[], citations=["x"], should_refuse=True, refused=False
        )
        assert refusal_correct(r) is False

    def test_shouldnt_refuse_did(self):
        r = _result(
            expected_sources=["a.md"],
            retrieved=[],
            citations=[],
            should_refuse=False,
            refused=True,
            refusal_reason="out_of_corpus",
        )
        assert refusal_correct(r) is False

    def test_shouldnt_refuse_didnt_returns_none(self):
        r = _result(
            expected_sources=["a.md"],
            retrieved=[_sc("a.md#0", "a.md")],
            citations=["a.md#0"],
            should_refuse=False,
            refused=False,
        )
        assert refusal_correct(r) is None

    def test_reason_mismatch(self):
        r = _result(
            expected_sources=[],
            retrieved=[],
            citations=[],
            should_refuse=True,
            refused=True,
            refusal_reason="out_of_corpus",
            expected_refusal_reason="ambiguous_query",
        )
        assert refusal_correct(r) is False

    def test_reason_match(self):
        r = _result(
            expected_sources=[],
            retrieved=[],
            citations=[],
            should_refuse=True,
            refused=True,
            refusal_reason="ambiguous_query",
            expected_refusal_reason="ambiguous_query",
        )
        assert refusal_correct(r) is True
