import math
from collections.abc import Iterable

from twin_mind.models.document import Chunk
from twin_mind.vectorstore.base import ScoredChunk


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}

    def add(self, chunks: list[Chunk]) -> None:
        for c in chunks:
            if c.embedding is None:
                raise ValueError(f"chunk {c.id} missing embedding")
            self._chunks[c.id] = c

    def search(self, query_embedding: list[float], k: int) -> list[ScoredChunk]:
        scored = [
            ScoredChunk(c, _cosine(query_embedding, c.embedding or []))
            for c in self._chunks.values()
        ]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:k]

    def all_chunks(self) -> Iterable[Chunk]:
        return list(self._chunks.values())

    def __len__(self) -> int:
        return len(self._chunks)
