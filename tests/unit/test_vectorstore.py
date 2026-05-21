import pytest

from twin_mind.models.document import Chunk, Source
from twin_mind.vectorstore.adapters.in_memory import InMemoryVectorStore
from twin_mind.vectorstore.factory import make_vectorstore


def _chunk(id_: str, vec: list[float]) -> Chunk:
    return Chunk(id=id_, doc_id="d", source=Source(name="s"), text="t", embedding=vec)


def test_in_memory_search_ranks_by_cosine():
    store = InMemoryVectorStore()
    store.add(
        [
            _chunk("a", [1.0, 0.0]),
            _chunk("b", [0.0, 1.0]),
            _chunk("c", [0.9, 0.1]),
        ]
    )
    out = store.search([1.0, 0.0], k=2)
    assert [s.chunk.id for s in out] == ["a", "c"]
    assert out[0].score > out[1].score


def test_rejects_missing_embedding():
    store = make_vectorstore("in_memory")
    bad = Chunk(id="x", doc_id="d", source=Source(name="s"), text="t")
    with pytest.raises(ValueError):
        store.add([bad])
