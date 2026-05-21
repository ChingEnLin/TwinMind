"""One-off verification of Phase 1 exit criteria 3 and 4.

Run with:  uv run python scripts/verify_phase1.py
"""

import asyncio
import json

from fastapi.testclient import TestClient

from twin_mind.api.app import create_app
from twin_mind.api.budget import budget
from twin_mind.api.state import state
from twin_mind.config import settings


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    body = body.replace("\r\n", "\n")
    out = []
    for frame in body.split("\n\n"):
        ev = data = None
        for line in frame.splitlines():
            if line.startswith("event:"):
                ev = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = line[len("data:") :].strip()
        if ev and data:
            out.append((ev, json.loads(data)))
    return out


async def verify_caching() -> None:
    print("=" * 60)
    print("CRITERION 3: prompt caching")
    print("=" * 60)

    retriever = state.ensure_index()
    retrieved = retriever.retrieve("What did Ching-En do at Virtonomy?")
    llm = state.llm()

    async def one_call(label: str) -> None:
        usage = None
        async for ev in llm.stream_answer(
            "What did Ching-En do at Virtonomy?",
            retrieved,
            max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
        ):
            if ev.kind == "done":
                usage = ev.usage
        assert usage is not None
        print(
            f"  {label}: input={usage.input_tokens} "
            f"output={usage.output_tokens} "
            f"cache_creation={usage.cache_creation_input_tokens} "
            f"cache_read={usage.cache_read_input_tokens}"
        )
        return usage

    first = await one_call("call 1")
    second = await one_call("call 2")

    if second.cache_read_input_tokens > 0:
        print(f"  PASS — cache_read_input_tokens={second.cache_read_input_tokens} on call 2")
    else:
        print("  FAIL — cache_read_input_tokens was 0 on the second call")
    print(f"  (call 1 cache_creation was {first.cache_creation_input_tokens})")


def verify_budget() -> None:
    print()
    print("=" * 60)
    print("CRITERION 4: BUDGET_EXCEEDED with DAILY_BUDGET_USD=0.01")
    print("=" * 60)

    # Lower the cap and pre-fill the spend counter so the next /v1/chat trips it.
    budget.daily_cap_usd = 0.01
    budget._spent_today_usd = 0.02

    app = create_app()
    client = TestClient(app)
    resp = client.post(
        "/v1/chat",
        json={"message": "What did Ching-En do at Virtonomy?"},
        headers={"Authorization": "Bearer dev-key"},
    )
    print(f"  HTTP status: {resp.status_code}")
    events = _parse_sse(resp.text)
    print(f"  SSE events: {[t for t, _ in events]}")

    if events and events[0][0] == "error" and events[0][1].get("code") == "BUDGET_EXCEEDED":
        msg = events[0][1]
        print(f"  PASS — got BUDGET_EXCEEDED, message={msg.get('message')!r}, "
              f"retry_after={msg.get('retry_after')}s")
    else:
        print("  FAIL — expected first event to be error/BUDGET_EXCEEDED")


async def main() -> None:
    await verify_caching()
    verify_budget()


if __name__ == "__main__":
    asyncio.run(main())
