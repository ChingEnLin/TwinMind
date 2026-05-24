from twin_mind.generation.citations import extract_cited_ids
from twin_mind.vectorstore.base import ScoredChunk

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


def enforce_grounding(
    answer: str, retrieved: list[ScoredChunk] | None = None
) -> tuple[str, bool, str | None]:
    """Return (final_answer, refused, refusal_reason).

    refusal_reason is one of:
      - "out_of_corpus": the corpus genuinely doesn't cover this question, OR
        the model cited only invented chunk IDs that don't resolve to any
        retrieved chunk (silent hallucination — force a refusal)
      - "ambiguous_query": the corpus might cover it but the question is too
        vague for the model to commit to an answer (clarification requested)

    Hardening: when ``retrieved`` is provided, we require at least one citation
    token to resolve to a real retrieved chunk. The earlier check (any bracket
    token present) was insufficient — a model could write "[invented_id_999]"
    and pass the citation check while the build_citations step silently
    dropped the unresolved ID, producing an answer with zero displayed
    sources. That's a hallucination route we now close.

    ``retrieved`` is optional for backward-compat with older test call sites.
    Production paths (chat route, eval runner) MUST pass it.
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

    if retrieved is not None:
        valid_ids = {s.chunk.id for s in retrieved}
        resolvable = [cid for cid in cited if cid in valid_ids]
        if not resolvable:
            return (
                f"{REFUSAL_TEXT} The answer referenced sources that aren't in the retrieved context.",
                True,
                "out_of_corpus",
            )

    return answer, False, None
