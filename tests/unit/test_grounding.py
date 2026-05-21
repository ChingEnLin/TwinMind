from twin_mind.generation.citations import build_citations, extract_cited_ids
from twin_mind.generation.grounding import enforce_grounding
from twin_mind.models.document import Chunk, Source
from twin_mind.vectorstore.base import ScoredChunk


def test_extract_cited_ids():
    txt = "He did X [a/b.md#1] and Y [c.md#2]. Repeat [a/b.md#1]."
    assert extract_cited_ids(txt) == ["a/b.md#1", "c.md#2"]


def test_enforce_grounding_passes_with_citation():
    final, refused, reason = enforce_grounding("did X [a#1].")
    assert refused is False
    assert reason is None
    assert final == "did X [a#1]."


def test_enforce_grounding_forces_refusal_when_no_citations():
    final, refused, reason = enforce_grounding("Just plain text.")
    assert refused is True
    assert reason == "out_of_corpus"
    assert "I don't have that" in final


def test_enforce_grounding_recognises_refusal_text():
    _, refused, reason = enforce_grounding("I don't have that in my notes.")
    assert refused is True
    assert reason == "out_of_corpus"


def test_build_citations_resolves_chunks():
    chunks = [
        ScoredChunk(
            Chunk(id="a#1", doc_id="a", source=Source(name="a.md", url="u"), text="t"),
            0.9,
        )
    ]
    cites = build_citations("answer [a#1].", chunks)
    assert len(cites) == 1
    assert cites[0].source == "a.md" and cites[0].url == "u"
