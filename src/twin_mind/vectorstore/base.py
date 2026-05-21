from dataclasses import dataclass
from typing import Protocol

from twin_mind.models.document import Chunk


@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float


class VectorStore(Protocol):
    def add(self, chunks: list[Chunk]) -> None: ...

    def search(self, query_embedding: list[float], k: int) -> list[ScoredChunk]: ...

    def __len__(self) -> int: ...
