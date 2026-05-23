"""Per-dimension eval metrics.

Each metric operates on an EvalResult and returns either a boolean or a
[0.0, 1.0] score. They are deliberately *independent* so we can move each
number on its own — see notes/07-three-kinds-of-failure.md.
"""

from twin_mind.eval.metrics.citation import citation_precision
from twin_mind.eval.metrics.refusal import refusal_correct
from twin_mind.eval.metrics.retrieval import retrieval_recall

__all__ = ["citation_precision", "refusal_correct", "retrieval_recall"]
