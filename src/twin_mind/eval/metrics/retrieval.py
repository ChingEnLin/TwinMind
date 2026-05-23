"""Retrieval recall@K.

Did at least one expected source appear in the retrieved chunks? Operates on
source.name (the document path), not chunk_id — chunk indices can shift when
chunking changes, but the source file is the stable identity.

Returns None (not applicable) when the case has no expected_sources, e.g.
refusal cases where any retrieval is acceptable.
"""

from twin_mind.eval.runner import EvalResult


def retrieval_recall(result: EvalResult) -> float | None:
    expected = result.case.expected_sources
    if not expected:
        return None
    retrieved_sources = {s.chunk.source.name for s in result.retrieved}
    hits = sum(1 for exp in expected if exp in retrieved_sources)
    return hits / len(expected)
