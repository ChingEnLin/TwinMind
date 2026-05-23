from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-haiku-4-5-20251001"
    LLM_MAX_OUTPUT_TOKENS: int = 400
    LLM_MAX_REFUSAL_TOKENS: int = 100
    LLM_JUDGE_MODEL: str = "claude-haiku-4-5-20251001"

    DAILY_BUDGET_USD: float = 0.50
    ALLOWED_ORIGIN: str = "http://localhost:5173"
    API_KEY: str = "dev-key"

    SAMPLES_DIR: str = "data/samples"

    TOP_K: int = 4
    CHUNK_TARGET_TOKENS: int = 400
    CHUNK_OVERLAP_TOKENS: int = 60
    CHUNK_STRATEGY: str = "token_aware"  # "paragraph" | "token_aware"
    MAX_CONTEXT_TOKENS: int = 1800

    # Adapter selection (Phase 2)
    EMBEDDER: str = "bge"  # "stub" | "bge"
    BGE_MODEL: str = "BAAI/bge-small-en-v1.5"
    VECTORSTORE: str = "chroma"  # "in_memory" | "chroma"
    CHROMA_PATH: str = "data/processed/chroma"
    CHROMA_COLLECTION: str = "twin_mind"

    # Anthropic Haiku 4.5 pricing (USD per 1M tokens). Update if pricing changes.
    PRICE_INPUT_PER_MTOK: float = 1.00
    PRICE_OUTPUT_PER_MTOK: float = 5.00
    PRICE_CACHE_WRITE_PER_MTOK: float = 1.25
    PRICE_CACHE_READ_PER_MTOK: float = 0.10

    @property
    def samples_path(self) -> Path:
        return Path(self.SAMPLES_DIR)


settings = Settings()
