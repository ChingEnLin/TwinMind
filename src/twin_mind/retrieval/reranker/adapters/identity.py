from twin_mind.vectorstore.base import ScoredChunk


class IdentityReranker:
    """No-op reranker: returns the first k candidates unchanged.

    Useful for testing the wiring without invoking a real model, and as the
    default when reranking is disabled.
    """

    name = "identity"

    def rerank(self, query: str, candidates: list[ScoredChunk], k: int) -> list[ScoredChunk]:
        return candidates[:k]
