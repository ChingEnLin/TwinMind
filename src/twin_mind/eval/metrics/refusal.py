"""Refusal correctness.

Two-part check:
1. Did the bot refuse iff the case said it should?
2. If it refused and the case specified expected_refusal_reason, does the
   refusal_reason code match?

Returns None for non-refusal cases where the bot did not refuse — those
are scored by retrieval/citation/groundedness, not by this metric.
"""

from twin_mind.eval.runner import EvalResult


def refusal_correct(result: EvalResult) -> bool | None:
    case = result.case
    if not case.should_refuse and not result.refused:
        return None
    if case.should_refuse != result.refused:
        return False
    if case.expected_refusal_reason is None:
        return True
    return result.refusal_reason == case.expected_refusal_reason
