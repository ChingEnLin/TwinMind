from twin_mind.models.document import Chunk, Source
from twin_mind.retrieval.bm25 import BM25Retriever, _tokenize


def _chunk(id_: str, text: str) -> Chunk:
    return Chunk(id=id_, doc_id="doc.md", source=Source(name="doc.md"), text=text)


def test_tokenize_lowercases_and_drops_stopwords():
    toks = _tokenize("The QuickBrown Fox is jumping and the lazy dog has snored")
    assert "quickbrown" in toks
    assert "jumping" in toks
    # stopwords removed (these are in the configured list)
    assert "the" not in toks
    assert "is" not in toks
    assert "and" not in toks
    assert "has" not in toks


def test_bm25_finds_exact_keyword():
    chunks = [
        _chunk("a", "QueryPal is built with FastAPI and React"),
        _chunk("b", "TwinMind is a RAG backend using Python and Anthropic Claude"),
        _chunk("c", "Some unrelated text about gardening and weather"),
    ]
    bm = BM25Retriever(chunks)
    hits = bm.retrieve("FastAPI React", k=2)
    assert hits, "expected at least one hit"
    assert hits[0].chunk.id == "a", f"expected 'a' first, got {[h.chunk.id for h in hits]}"


def test_bm25_empty_query_returns_nothing():
    chunks = [_chunk("a", "some content")]
    bm = BM25Retriever(chunks)
    assert bm.retrieve("the and or but", k=5) == []


def test_bm25_no_corpus_no_results():
    bm = BM25Retriever([])
    assert bm.retrieve("anything", k=5) == []
