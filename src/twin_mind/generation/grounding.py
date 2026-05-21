from twin_mind.generation.citations import extract_cited_ids

REFUSAL_TEXT = "I don't have that in my notes."


def is_refusal(answer: str) -> bool:
    return answer.strip().lower().startswith("i don't have that in my notes")


def enforce_grounding(answer: str) -> tuple[str, bool, str | None]:
    """Return (final_answer, refused, refusal_reason).

    If the answer is already a refusal, pass it through.
    If the answer has zero citations, force a refusal — the model claimed something
    we can't trace back to a chunk.
    """
    if is_refusal(answer):
        return answer, True, "out_of_corpus"

    cited = extract_cited_ids(answer)
    if not cited:
        return (
            f"{REFUSAL_TEXT} The retrieved context did not support a grounded answer.",
            True,
            "out_of_corpus",
        )
    return answer, False, None
