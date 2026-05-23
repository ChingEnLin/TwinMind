"""Citation precision.

Of the citations the bot emitted, what fraction resolve to a chunk whose
source appears in the case's expected_sources? Catches over-citing and
wrong-source bugs.

Returns None (not applicable) when:
- the case has no expected_sources (refusal cases), or
- the bot refused (no citations to score).
"""

from twin_mind.eval.runner import EvalResult


def citation_precision(result: EvalResult) -> float | None:
    if result.refused or not result.case.expected_sources:
        return None
    if not result.citations:
        return 0.0
    expected = set(result.case.expected_sources)
    by_id = {s.chunk.id: s.chunk.source.name for s in result.retrieved}
    hits = sum(1 for cid in result.citations if by_id.get(cid) in expected)
    return hits / len(result.citations)
