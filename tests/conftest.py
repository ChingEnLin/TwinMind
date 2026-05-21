from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest

from twin_mind.generation.base import LLMStreamEvent, LLMUsage
from twin_mind.vectorstore.base import ScoredChunk


@dataclass
class FakeLLM:
    """Deterministic streaming LLM stub for tests."""

    chunks_text: str = (
        "At Virtonomy, Ching-En built a Python ingestion pipeline [experience/virtonomy.md#1]."
    )
    usage: LLMUsage | None = None

    async def stream_answer(
        self,
        question: str,
        chunks: list[ScoredChunk],
        max_tokens: int,
    ) -> AsyncIterator[LLMStreamEvent]:
        assert max_tokens > 0, "max_tokens must be set"
        # If we got at least one retrieved chunk, prefer its id in the citation so
        # the integration test's grounding check passes.
        text = self.chunks_text
        if chunks:
            cid = chunks[0].chunk.id
            text = f"At Virtonomy, Ching-En built a Python ingestion pipeline [{cid}]."
        for piece in text.split(" "):
            yield LLMStreamEvent(kind="token", text=piece + " ")
        yield LLMStreamEvent(
            kind="done",
            usage=self.usage or LLMUsage(input_tokens=1000, output_tokens=50),
        )


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()
