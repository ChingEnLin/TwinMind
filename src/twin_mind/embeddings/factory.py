from twin_mind.embeddings.adapters.stub import StubEmbedder
from twin_mind.embeddings.base import Embedder


def make_embedder(name: str = "stub") -> Embedder:
    if name == "stub":
        return StubEmbedder()
    raise ValueError(f"unknown embedder: {name}")
