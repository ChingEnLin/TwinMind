from collections.abc import AsyncIterator
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from twin_mind.config import settings
from twin_mind.generation.base import LLMStreamEvent, LLMUsage
from twin_mind.vectorstore.base import ScoredChunk

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
_env = Environment(
    loader=FileSystemLoader(str(_PROMPT_DIR)),
    autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
    keep_trailing_newline=True,
)


def render_system_prompt() -> str:
    return _env.get_template("system.j2").render()


def render_user_prompt(question: str, chunks: list[ScoredChunk]) -> str:
    return _env.get_template("answer.j2").render(question=question, chunks=chunks)


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        from anthropic import AsyncAnthropic

        key = api_key or settings.ANTHROPIC_API_KEY
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.client = AsyncAnthropic(api_key=key)
        self.model = model or settings.LLM_MODEL

    async def stream_answer(
        self,
        question: str,
        chunks: list[ScoredChunk],
        max_tokens: int,
    ) -> AsyncIterator[LLMStreamEvent]:
        if not max_tokens or max_tokens <= 0:
            raise ValueError("max_tokens must be > 0 — required to bound cost")

        system_blocks = [
            {
                "type": "text",
                "text": render_system_prompt(),
                "cache_control": {"type": "ephemeral"},
            }
        ]
        user_text = render_user_prompt(question, chunks)

        usage = LLMUsage(input_tokens=0, output_tokens=0)

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system_blocks,
            messages=[{"role": "user", "content": user_text}],
        ) as stream:
            async for text_delta in stream.text_stream:
                if text_delta:
                    yield LLMStreamEvent(kind="token", text=text_delta)
            final = await stream.get_final_message()
            u = getattr(final, "usage", None)
            if u is not None:
                usage = LLMUsage(
                    input_tokens=getattr(u, "input_tokens", 0) or 0,
                    output_tokens=getattr(u, "output_tokens", 0) or 0,
                    cache_read_input_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
                    cache_creation_input_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
                )

        yield LLMStreamEvent(kind="done", usage=usage)
