from twin_mind.embeddings.adapters.stub import StubEmbedder
from twin_mind.embeddings.factory import make_embedder


def test_stub_embedder_deterministic_and_normalized():
    e = StubEmbedder(dim=64)
    [v1] = e.embed(["hello world"])
    [v2] = e.embed(["hello world"])
    assert v1 == v2
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_factory_returns_stub():
    e = make_embedder("stub")
    assert e.name == "stub"
    assert e.dim > 0
