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

    # Ingestion source. data/samples/private/ is the authoritative corpus
    # (synced from the GCS bucket at CI time). The other subdirs of
    # data/samples/ (background.md, experience/, projects/) are legacy/dev
    # fixtures and intentionally NOT walked by the loader.
    SAMPLES_DIR: str = "data/samples/private"

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

    # GitHub ingestion (Phase 3)
    GITHUB_TOKEN: str = ""
    GITHUB_USER: str = "ChingEnLin"
    GITHUB_DENYLIST: list[str] = ["KuaMongous", "NoteyFit"]
    GITHUB_INCLUDE_DOCS: bool = True

    # Source used for the lazy server-boot ingest when the store is empty.
    # Use "all" or "github" if you want the server to fetch on first boot.
    BOOTSTRAP_SOURCE: str = "local"

    # Hybrid retrieval (Phase 3)
    RETRIEVAL_MODE: str = "hybrid"  # "vector" | "bm25" | "hybrid"
    RRF_K: int = 60
    HYBRID_PER_RETRIEVER_K: int = 20

    # Reranking (Phase 5)
    RERANKER: str = "claude"  # "none" | "identity" | "cross_encoder" | "claude"
    RERANKER_CANDIDATE_K: int = 20
    CROSS_ENCODER_MODEL: str = "BAAI/bge-reranker-base"
    CLAUDE_RERANK_MODEL: str = "claude-haiku-4-5-20251001"

    # Anthropic Haiku 4.5 pricing (USD per 1M tokens). Update if pricing changes.
    PRICE_INPUT_PER_MTOK: float = 1.00
    PRICE_OUTPUT_PER_MTOK: float = 5.00
    PRICE_CACHE_WRITE_PER_MTOK: float = 1.25
    PRICE_CACHE_READ_PER_MTOK: float = 0.10

    @property
    def samples_path(self) -> Path:
        return Path(self.SAMPLES_DIR)


settings = Settings()
