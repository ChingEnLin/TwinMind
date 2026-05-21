from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from twin_mind.vectorstore.base import ScoredChunk


@dataclass
class LLMUsage:
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class LLMStreamEvent:
    kind: str  # "token" | "done"
    text: str = ""
    usage: LLMUsage | None = None


class LLMClient(Protocol):
    async def stream_answer(
        self,
        question: str,
        chunks: list[ScoredChunk],
        max_tokens: int,
    ) -> AsyncIterator[LLMStreamEvent]: ...
