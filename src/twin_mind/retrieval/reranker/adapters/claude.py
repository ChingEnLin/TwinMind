"""Claude-as-judge listwise reranker.

A single Anthropic call scores all candidates jointly and returns a reordered
list of integer indices. Listwise (one call) rather than pointwise (N calls)
because:
- N calls = N × per-request overhead and a fixed cache-write cost per call
- One call lets the model compare candidates against each other, which is
  the actual signal we care about for ordering
- One call is cheaper for typical N=20: ~$0.001-0.003 vs ~$0.01-0.02

Tradeoff: the model has to keep all candidates in working memory, which
caps usable candidate_k around 20-30 for Haiku. Past that, quality of the
ranking degrades and we should switch to pairwise or a cheaper reranker.

Robustness: if the model returns malformed JSON or fewer indices than
expected, we fall back to the input order (acts like IdentityReranker for
that query). Better than crashing the retrieval path on a transient parse
failure.
"""

from __future__ import annotations

import json
import re

from twin_mind.config import settings
from twin_mind.vectorstore.base import ScoredChunk

_SYSTEM = (
    "You are a relevance scorer for a retrieval system. Given a query and a "
    "numbered list of candidate passages, return a JSON array of the candidate "
    "indices in descending order of relevance to the query. Only output the "
    "JSON array — no prose, no markdown, no explanation. Every index from the "
    "input must appear exactly once. Indices are 0-based."
)

_MAX_CHARS_PER_CANDIDATE = 500


def _build_user_prompt(query: str, candidates: list[ScoredChunk]) -> str:
    lines = [f"Query: {query}", "", "Candidates:"]
    for i, sc in enumerate(candidates):
        text = sc.chunk.text.strip().replace("\n", " ")
        if len(text) > _MAX_CHARS_PER_CANDIDATE:
            text = text[:_MAX_CHARS_PER_CANDIDATE] + "..."
        lines.append(f"[{i}] (source: {sc.chunk.source.name}) {text}")
    lines.append("")
    lines.append(
        f"Return a JSON array of {len(candidates)} integers — the indices of "
        "all candidates above, ordered from most to least relevant to the query."
    )
    return "\n".join(lines)


def _parse_ranking(raw: str, n: int) -> list[int] | None:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[^\]]+\]", text)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(parsed, list):
        return None
    seen: set[int] = set()
    order: list[int] = []
    for item in parsed:
        if not isinstance(item, int) or item < 0 or item >= n or item in seen:
            continue
        seen.add(item)
        order.append(item)
    # Fill missing indices in original order so we always return n positions.
    for i in range(n):
        if i not in seen:
            order.append(i)
    return order


class ClaudeReranker:
    name = "claude"

    def __init__(self, model: str | None = None) -> None:
        from anthropic import Anthropic

        key = settings.ANTHROPIC_API_KEY
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.client = Anthropic(api_key=key)
        self.model = model or settings.CLAUDE_RERANK_MODEL

    def rerank(self, query: str, candidates: list[ScoredChunk], k: int) -> list[ScoredChunk]:
        if not candidates:
            return []
        if len(candidates) == 1:
            return candidates[:k]

        user = _build_user_prompt(query, candidates)
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=256,
                system=_SYSTEM,
                messages=[{"role": "user", "content": user}],
            )
            raw = "".join(
                block.text for block in resp.content if getattr(block, "type", None) == "text"
            )
        except Exception:
            return candidates[:k]

        order = _parse_ranking(raw, len(candidates))
        if order is None:
            return candidates[:k]

        # Re-score: top position gets highest synthetic score so downstream
        # consumers that care about ordering see a monotonic sequence.
        n = len(order)
        reordered = [
            ScoredChunk(candidates[idx].chunk, float(n - rank)) for rank, idx in enumerate(order)
        ]
        return reordered[:k]
