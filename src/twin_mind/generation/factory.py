from twin_mind.generation.adapters.anthropic import AnthropicLLM
from twin_mind.generation.base import LLMClient


def make_llm(name: str = "anthropic") -> LLMClient:
    if name == "anthropic":
        return AnthropicLLM()
    raise ValueError(f"unknown llm: {name}")
