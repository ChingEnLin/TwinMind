from twin_mind.embeddings.base import Embedder


def make_embedder(name: str = "stub") -> Embedder:
    if name == "stub":
        from twin_mind.embeddings.adapters.stub import StubEmbedder

        return StubEmbedder()
    if name == "bge":
        from twin_mind.embeddings.adapters.bge import BGEEmbedder

        return BGEEmbedder()
    raise ValueError(f"unknown embedder: {name}")
