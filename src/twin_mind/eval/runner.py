from dataclasses import dataclass
from pathlib import Path

import yaml

from twin_mind.api.state import AppState
from twin_mind.config import settings
from twin_mind.generation.citations import build_citations
from twin_mind.generation.grounding import enforce_grounding


@dataclass
class EvalCase:
    question: str
    expected_sources: list[str]
    should_refuse: bool
    requires_github: bool = False


@dataclass
class EvalResult:
    case: EvalCase
    answer: str
    refused: bool
    citations: list[str]
    passed: bool
    reason: str = ""
    skipped: bool = False


def load_cases(path: str | Path) -> list[EvalCase]:
    data = yaml.safe_load(Path(path).read_text())
    cases = []
    for item in data["cases"]:
        cases.append(
            EvalCase(
                question=item["question"],
                expected_sources=list(item.get("expected_sources") or []),
                should_refuse=bool(item.get("should_refuse", False)),
                requires_github=bool(item.get("requires_github", False)),
            )
        )
    return cases


async def run_case(state_obj: AppState, case: EvalCase) -> EvalResult:
    retriever = state_obj.ensure_index()
    # Skip GitHub-dependent cases if the corpus doesn't contain any github/ chunks.
    if case.requires_github:
        has_github = any(c.id.startswith("github/") for c in retriever.store.all_chunks())
        if not has_github:
            return EvalResult(
                case=case,
                answer="",
                refused=False,
                citations=[],
                passed=True,
                reason="skipped: requires github ingest",
                skipped=True,
            )
    retrieved = retriever.retrieve(case.question)
    llm = state_obj.llm()

    full = ""
    async for ev in llm.stream_answer(
        case.question, retrieved, max_tokens=settings.LLM_MAX_OUTPUT_TOKENS
    ):
        if ev.kind == "token":
            full += ev.text

    final, refused, _ = enforce_grounding(full)
    citations = [c.id for c in build_citations(final, retrieved)]

    if case.should_refuse:
        passed = refused
        reason = "" if passed else "expected refusal but answered"
    else:
        if refused:
            passed = False
            reason = "expected grounded answer but model refused"
        else:
            by_id = {s.chunk.id: s.chunk.source.name for s in retrieved}
            cited_chunk_sources = {by_id[c] for c in citations if c in by_id}
            if not case.expected_sources:
                passed = bool(citations)
            else:
                passed = any(exp in cited_chunk_sources for exp in case.expected_sources)
            reason = (
                "" if passed else f"no expected source cited; cited={sorted(cited_chunk_sources)}"
            )

    return EvalResult(
        case=case,
        answer=final,
        refused=refused,
        citations=citations,
        passed=passed,
        reason=reason,
    )
