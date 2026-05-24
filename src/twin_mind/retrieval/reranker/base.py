from typing import Protocol

from twin_mind.vectorstore.base import ScoredChunk


class Reranker(Protocol):
    name: str

    def rerank(
        self, query: str, candidates: list[ScoredChunk], k: int
    ) -> list[ScoredChunk]: ...
