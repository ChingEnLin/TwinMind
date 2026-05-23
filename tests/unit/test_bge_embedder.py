"""BGE embedder tests.

These hit the local sentence-transformers model. Skipped if not installed.
The model is small (~130MB) but downloads on first run, so we mark slow
and rely on local CI to cache.
"""

import os

import pytest

pytest.importorskip("sentence_transformers")

# Allow CI to opt out by setting TWINMIND_SKIP_BGE=1 (avoids ~130MB download).
if os.environ.get("TWINMIND_SKIP_BGE") == "1":
    pytest.skip("BGE tests disabled via TWINMIND_SKIP_BGE", allow_module_level=True)

from twin_mind.embeddings.adapters.bge import BGEEmbedder  # noqa: E402


@pytest.fixture(scope="module")
def bge() -> BGEEmbedder:
    return BGEEmbedder()


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_bge_output_shape_and_normalization(bge: BGEEmbedder):
    vecs = bge.embed(["hello world"])
    assert len(vecs) == 1
    assert len(vecs[0]) == bge.dim
    # normalize_embeddings=True → unit length
    norm = sum(v * v for v in vecs[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-3


def test_bge_semantic_neighbors_beat_unrelated(bge: BGEEmbedder):
    # Paraphrase pair should score higher than unrelated pair.
    a, b, c = bge.embed(
        [
            "Ching-En built an ingestion pipeline for medical CAD files",
            "He developed a pipeline that processed medical-device geometry",
            "The capital of France is Paris",
        ]
    )
    sim_pair = _cos(a, b)
    sim_unrelated = _cos(a, c)
    assert sim_pair > sim_unrelated, (
        f"paraphrase ({sim_pair:.3f}) should beat unrelated ({sim_unrelated:.3f})"
    )


def test_bge_query_prefix_applied(bge: BGEEmbedder):
    # The query path differs from the document path (prefix is applied).
    doc_vec = bge.embed(["medical device simulation"])[0]
    q_vec = bge.embed_queries(["medical device simulation"])[0]
    assert doc_vec != q_vec, "query embedding should differ from document embedding"
