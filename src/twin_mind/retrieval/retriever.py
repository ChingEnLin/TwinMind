from twin_mind.embeddings.base import Embedder
from twin_mind.vectorstore.base import ScoredChunk, VectorStore


class Retriever:
    def __init__(self, embedder: Embedder, store: VectorStore, top_k: int = 4) -> None:
        self.embedder = embedder
        self.store = store
        self.top_k = top_k

    def retrieve(self, query: str, k: int | None = None) -> list[ScoredChunk]:
        # Some embedders (e.g. BGE) need a query-side prefix for retrieval quality.
        embed_q = getattr(self.embedder, "embed_queries", None)
        if callable(embed_q):
            [vec] = embed_q([query])
        else:
            [vec] = self.embedder.embed([query])
        return self.store.search(vec, k or self.top_k)
