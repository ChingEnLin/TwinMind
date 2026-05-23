"""Claude-as-judge groundedness scoring.

Calls Anthropic Haiku to score whether the answer's factual claims are
supported by the cited chunks. This is the only metric that costs $ per
eval run — keep it gated behind the `run-eval` label in CI.

Output: float in [0.0, 1.0] plus a short rationale.
- 1.0: every claim in the answer is directly supported by a chunk
- 0.0: claims are unsupported / hallucinated
- None: refusal cases (no answer to judge)

Returns None on transient API failures rather than raising — a flaky judge
should not fail the suite. The failure is logged via the rationale.
"""

import json
from dataclasses import dataclass

from twin_mind.config import settings
from twin_mind.eval.runner import EvalResult

_JUDGE_PROMPT = """You are evaluating whether an AI assistant's answer is grounded in the source chunks it was given.

Score from 0.0 to 1.0:
- 1.0 means every factual claim in the answer is directly supported by at least one chunk.
- 0.5 means the answer mixes supported and unsupported claims.
- 0.0 means the answer is largely hallucinated or contradicts the chunks.

Ignore stylistic differences. Only judge whether the claims are supported.

Respond with ONLY a JSON object of the form:
{{"score": 0.0-1.0, "rationale": "one short sentence"}}

Question:
{question}

Chunks provided to the assistant:
{chunks}

Assistant's answer:
{answer}
"""


@dataclass
class JudgeVerdict:
    score: float
    rationale: str


async def groundedness_score(result: EvalResult) -> JudgeVerdict | None:
    if result.refused or not result.retrieved:
        return None

    from anthropic import AsyncAnthropic

    key = settings.ANTHROPIC_API_KEY
    if not key:
        return JudgeVerdict(score=0.0, rationale="no ANTHROPIC_API_KEY — judge skipped")

    chunks_text = "\n\n".join(
        f"[{s.chunk.id}] ({s.chunk.source.name})\n{s.chunk.text}" for s in result.retrieved
    )
    prompt = _JUDGE_PROMPT.format(
        question=result.case.question,
        chunks=chunks_text,
        answer=result.answer,
    )

    client = AsyncAnthropic(api_key=key)
    try:
        msg = await client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        return JudgeVerdict(score=0.0, rationale=f"judge api error: {exc}")

    raw = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(raw)
        score = float(data.get("score", 0.0))
        rationale = str(data.get("rationale", ""))[:200]
        score = max(0.0, min(1.0, score))
        return JudgeVerdict(score=score, rationale=rationale)
    except (json.JSONDecodeError, ValueError, TypeError):
        return JudgeVerdict(score=0.0, rationale=f"unparseable judge output: {raw[:80]!r}")
