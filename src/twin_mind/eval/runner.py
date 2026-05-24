from dataclasses import dataclass, field
from pathlib import Path

import yaml

from twin_mind.api.state import AppState
from twin_mind.config import settings
from twin_mind.generation.citations import build_citations
from twin_mind.generation.grounding import enforce_grounding
from twin_mind.retrieval.retriever import ScoredChunk


@dataclass
class EvalCase:
    question: str
    expected_sources: list[str]
    should_refuse: bool
    id: str = ""
    category: str = "uncategorized"
    expected_refusal_reason: str | None = None
    requires_github: bool = False


@dataclass
class EvalResult:
    case: EvalCase
    answer: str
    refused: bool
    refusal_reason: str | None
    citations: list[str]
    retrieved: list[ScoredChunk] = field(default_factory=list)
    passed: bool = False
    reason: str = ""
    skipped: bool = False


def load_cases(path: str | Path) -> list[EvalCase]:
    data = yaml.safe_load(Path(path).read_text())
    cases = []
    for i, item in enumerate(data["cases"], 1):
        case_id = item.get("id") or f"{item.get('category', 'case')}-{i:03d}"
        cases.append(
            EvalCase(
                id=str(case_id),
                question=item["question"],
                expected_sources=list(item.get("expected_sources") or []),
                should_refuse=bool(item.get("should_refuse", False)),
                category=str(item.get("category", "uncategorized")),
                expected_refusal_reason=item.get("expected_refusal_reason"),
                requires_github=bool(item.get("requires_github", False)),
            )
        )
    return cases


async def run_case(state_obj: AppState, case: EvalCase) -> EvalResult:
    retriever = state_obj.ensure_index()
    if case.requires_github:
        has_github = any(c.id.startswith("github/") for c in retriever.store.all_chunks())
        if not has_github:
            return EvalResult(
                case=case,
                answer="",
                refused=False,
                refusal_reason=None,
                citations=[],
                retrieved=[],
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

    final, refused, refusal_reason = enforce_grounding(full, retrieved)
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
        refusal_reason=refusal_reason,
        citations=citations,
        retrieved=retrieved,
        passed=passed,
        reason=reason,
    )
