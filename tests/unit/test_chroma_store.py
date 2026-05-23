import uuid

import pytest

chromadb = pytest.importorskip("chromadb")

from twin_mind.models.document import Chunk, Source  # noqa: E402
from twin_mind.vectorstore.adapters.chroma import ChromaVectorStore  # noqa: E402


def _unique_name() -> str:
    return f"test_{uuid.uuid4().hex[:12]}"


def _chunk(id_: str, text: str, vec: list[float]) -> Chunk:
    return Chunk(
        id=id_,
        doc_id="doc.md",
        source=Source(name="doc.md"),
        text=text,
        section="Section A",
        embedding=vec,
    )


def test_chroma_roundtrip_and_search():
    store = ChromaVectorStore(in_memory=True, collection=_unique_name())
    assert len(store) == 0

    store.add(
        [
            _chunk("a", "alpha cat", [1.0, 0.0, 0.0]),
            _chunk("b", "beta dog", [0.0, 1.0, 0.0]),
            _chunk("c", "gamma bird", [0.0, 0.0, 1.0]),
        ]
    )
    assert len(store) == 3

    results = store.search([0.9, 0.1, 0.0], k=2)
    assert len(results) == 2
    ids = [r.chunk.id for r in results]
    assert ids[0] == "a", f"expected 'a' to rank first, got {ids}"
    # similarity should be in [-1, 1] and descending
    assert results[0].score >= results[1].score
    assert -1.01 <= results[0].score <= 1.01

    # metadata round-trip
    a = next(r for r in results if r.chunk.id == "a")
    assert a.chunk.source.name == "doc.md"
    assert a.chunk.section == "Section A"
    assert a.chunk.text == "alpha cat"


def test_chroma_upsert_is_idempotent():
    store = ChromaVectorStore(in_memory=True, collection=_unique_name())
    c = _chunk("x", "first", [1.0, 0.0])
    store.add([c])
    store.add([c])  # second add of same id should not duplicate
    assert len(store) == 1


def test_chroma_reset_drops_collection():
    store = ChromaVectorStore(in_memory=True, collection=_unique_name())
    store.add([_chunk("x", "first", [1.0, 0.0])])
    assert len(store) == 1
    store.reset()
    assert len(store) == 0
