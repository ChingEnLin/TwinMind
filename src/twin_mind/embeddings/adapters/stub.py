import hashlib
import math
import re

_WORD_RE = re.compile(r"[A-Za-z0-9]+")


class StubEmbedder:
    """Deterministic bag-of-words hashing embedder. Phase 1 only — no real semantics,
    but stable enough that identical-word queries find matching chunks."""

    name = "stub"

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = _WORD_RE.findall(text.lower())
        if not tokens:
            return vec
        for tok in tokens:
            h = hashlib.md5(tok.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            sign = 1.0 if (h[4] & 1) else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]
