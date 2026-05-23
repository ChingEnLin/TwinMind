from twin_mind.generation.citations import extract_cited_ids

REFUSAL_TEXT = "I don't have that in my notes."

# Phrases the model uses when it refuses *because the query is too vague*,
# not because the corpus is empty. Distinguishing these matters for UX —
# see notes/07-three-kinds-of-failure.md.
_AMBIGUITY_PHRASES = (
    "is incomplete",
    "please ask",
    "could you clarify",
    "could you tell me more",
    "what would you like to know",
    "what specifically",
    "more specific",
    "be more specific",
    "clarification",
)


def is_refusal(answer: str) -> bool:
    return answer.strip().lower().startswith("i don't have that in my notes")


def _looks_ambiguous(answer: str) -> bool:
    lowered = answer.lower()
    return any(phrase in lowered for phrase in _AMBIGUITY_PHRASES)


def enforce_grounding(answer: str) -> tuple[str, bool, str | None]:
    """Return (final_answer, refused, refusal_reason).

    refusal_reason is one of:
      - "out_of_corpus": the corpus genuinely doesn't cover this question
      - "ambiguous_query": the corpus might cover it but the question is too
        vague for the model to commit to an answer (clarification requested)

    If the answer has zero citations, force a refusal — the model claimed
    something we can't trace back to a chunk.
    """
    if is_refusal(answer):
        reason = "ambiguous_query" if _looks_ambiguous(answer) else "out_of_corpus"
        return answer, True, reason

    cited = extract_cited_ids(answer)
    if not cited:
        return (
            f"{REFUSAL_TEXT} The retrieved context did not support a grounded answer.",
            True,
            "out_of_corpus",
        )
    return answer, False, None
