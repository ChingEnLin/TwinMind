"""Local sentence-transformers BGE embedder.

BGE-small-en-v1.5 is a 384-dim general-purpose English embedder. It expects an
asymmetric setup at retrieval time: the query is prefixed with a short
instruction; documents are embedded as-is. Cosine similarity is used.
"""

from __future__ import annotations

from threading import Lock

from twin_mind.config import settings

# BGE's documented retrieval instruction. Applied to QUERIES only.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class BGEEmbedder:
    name = "bge"

    def __init__(self, model_name: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name or settings.BGE_MODEL
        self._model = SentenceTransformer(self.model_name)
        get_dim = getattr(
            self._model, "get_embedding_dimension", self._model.get_sentence_embedding_dimension
        )
        self.dim = int(get_dim() or 384)
        self._lock = Lock()

    def _encode(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            vecs = self._model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        return vecs.tolist()

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed documents/chunks (no prefix)."""
        return self._encode(texts)

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Embed queries (with BGE's retrieval instruction prefix)."""
        return self._encode([_BGE_QUERY_PREFIX + t for t in texts])
