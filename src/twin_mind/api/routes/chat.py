import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from twin_mind.api.auth import require_api_key
from twin_mind.api.budget import BudgetExceeded, budget
from twin_mind.api.schemas import ChatRequest
from twin_mind.api.state import state
from twin_mind.config import settings
from twin_mind.generation.citations import build_citations, extract_cited_ids
from twin_mind.generation.grounding import REFUSAL_TEXT, enforce_grounding
from twin_mind.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _event(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data, separators=(",", ":"))}


async def _stream(req: ChatRequest, request_id: str) -> AsyncIterator[dict]:
    try:
        budget.check()
    except BudgetExceeded as e:
        yield _event(
            "error",
            {
                "code": "BUDGET_EXCEEDED",
                "message": "Daily budget reached. The chatbot will be back tomorrow.",
                "retry_after": e.remaining_seconds,
            },
        )
        return

    retriever = state.ensure_index()
    retrieved = retriever.retrieve(req.message)

    meta_retrieved = [
        {
            "id": s.chunk.id,
            "source": s.chunk.source.name,
            "section": s.chunk.section,
            "score": round(float(s.score), 4),
            "url": s.chunk.source.url,
        }
        for s in retrieved
    ]
    yield _event("meta", {"request_id": request_id, "retrieved": meta_retrieved})

    if not retrieved:
        msg = f"{REFUSAL_TEXT} No documents are indexed."
        yield _event("token", {"text": msg})
        yield _event(
            "done",
            {
                "refused": True,
                "refusal_reason": "out_of_corpus",
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": 0.0,
            },
        )
        return

    llm = state.llm()
    full = ""
    emitted_citations: set[str] = set()
    usage = None

    try:
        async for ev in llm.stream_answer(
            req.message, retrieved, max_tokens=settings.LLM_MAX_OUTPUT_TOKENS
        ):
            if ev.kind == "token" and ev.text:
                full += ev.text
                yield _event("token", {"text": ev.text})
                # Emit citation events as new IDs appear in the streamed text.
                cited = extract_cited_ids(full)
                by_id = {s.chunk.id: s.chunk for s in retrieved}
                for cid in cited:
                    if cid in emitted_citations or cid not in by_id:
                        continue
                    ch = by_id[cid]
                    emitted_citations.add(cid)
                    yield _event(
                        "citation",
                        {
                            "id": ch.id,
                            "source": ch.source.name,
                            "section": ch.section,
                            "url": ch.source.url,
                        },
                    )
            elif ev.kind == "done":
                usage = ev.usage
    except Exception as exc:  # noqa: BLE001
        logger.exception("anthropic upstream failure: %s", exc)
        yield _event(
            "error",
            {"code": "UPSTREAM_ERROR", "message": "LLM upstream failure."},
        )
        return

    final_answer, refused, refusal_reason = enforce_grounding(full, retrieved)
    if refused and final_answer != full:
        # The model didn't cite anything — surface the forced-refusal text as a final token
        # so the widget sees the corrected message.
        yield _event("token", {"text": "\n\n" + final_answer})

    cost = 0.0
    tokens_in = 0
    tokens_out = 0
    if usage is not None:
        cost = budget.record(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_input_tokens=usage.cache_read_input_tokens,
            cache_creation_input_tokens=usage.cache_creation_input_tokens,
        )
        tokens_in = (
            usage.input_tokens + usage.cache_read_input_tokens + usage.cache_creation_input_tokens
        )
        tokens_out = usage.output_tokens
        logger.info(
            "chat done req=%s in=%d out=%d cache_r=%d cache_w=%d cost=$%.5f",
            request_id,
            usage.input_tokens,
            usage.output_tokens,
            usage.cache_read_input_tokens,
            usage.cache_creation_input_tokens,
            cost,
        )

    # Make sure citations for any retrieved chunks referenced in the final
    # (possibly mutated) answer are emitted.
    for c in build_citations(final_answer, retrieved):
        if c.id in emitted_citations:
            continue
        emitted_citations.add(c.id)
        yield _event(
            "citation",
            {"id": c.id, "source": c.source, "section": c.section, "url": c.url},
        )

    yield _event(
        "done",
        {
            "refused": refused,
            "refusal_reason": refusal_reason,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": round(cost, 6),
        },
    )


@router.post("/chat", dependencies=[Depends(require_api_key)])
async def chat(body: ChatRequest, request: Request) -> EventSourceResponse:
    request_id = getattr(request.state, "request_id", "req_unknown")
    return EventSourceResponse(_stream(body, request_id))
