# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

TwinMind is a "Digital Twin" RAG chatbot backend: strict grounding (refuses out-of-corpus), citation-required answers, pluggable provider adapters, and cost discipline. Production stack: Anthropic Haiku 4.5 with prompt caching, BGE-small embeddings, Chroma persistent store, hybrid retrieval (vector + BM25 via RRF) followed by a single-call Haiku listwise reranker.

Reference docs live in `docs/` (ARCHITECTURE.md, API.md, EVAL.md, DEPLOYMENT.md, DECISIONS.md). These are committed and meant to be readable on GitHub. The `notes/` directory holds chronological learning notes — still gitignored, local reference only.

GitHub default branch is `dev` (not `main`). Push to `origin dev`.

## Commands

Dependencies use `uv`. Build/test entry points are in the Makefile:

- `make install` — `uv sync --extra dev`
- `make ingest` — load `data/samples/` into the in-memory index via `tm ingest --source local`
- `make query Q="..."` — one-shot CLI query
- `make serve` — FastAPI on `:8000` (`uvicorn twin_mind.api.app:app --reload`)
- `make test` — `uv run pytest -q` (asyncio_mode=auto, testpaths=tests)
- `make lint` — `ruff check` + `ruff format --check` over `src tests`
- `make e2e` — smoke eval (`tm eval --suite smoke`) against the **real** Anthropic API; costs money

Run a single test: `uv run pytest tests/contract/test_sse.py -q` or `uv run pytest -k <pattern>`.

`scripts/verify_phase1.py` exercises exit criteria 3 (prompt-cache hit) and 4 (BUDGET_EXCEEDED) against the real API. It is deliberately **outside** `tests/` so it doesn't spend money on every CI push. Invoke with `uv run python scripts/verify_phase1.py`.

Requires `ANTHROPIC_API_KEY` in `.env` (see `.env.example`).

## Architecture

Layered pipeline with provider-pluggable adapters. Each layer has `base.py` (Protocol/dataclasses), `factory.py` (string-keyed selector), and `adapters/` (concrete implementations). Swapping providers means adding an adapter and a factory branch — no caller changes.

```
ingestion → chunking → embeddings → vectorstore → retrieval → reranker → generation → api
```

- **ingestion** (`ingestion/local_docs.py`): walks `data/samples/`, yields `Document`s keyed by relative path.
- **chunking** (`chunking/strategies.py`): paragraph splits on blank lines; attaches nearest `##` header as `section`. Headers are **stripped from each paragraph's leading lines** before the body check — otherwise a paragraph whose first line is `#` would be dropped, killing all retrieval. Don't reintroduce a naive `startswith("#")` filter.
- **embeddings** (`embeddings/adapters/stub.py`): hash-based bag-of-words, dim=256, L2-normalized. Deterministic, no ML dependency.
- **vectorstore** (`vectorstore/adapters/in_memory.py`): dict + cosine similarity. Single process, not persisted.
- **retrieval** (`retrieval/retriever.py`): top-K from store via embedder. `retrieval/hybrid.py` fuses vector + BM25 via RRF when `RETRIEVAL_MODE=hybrid` (default).
- **reranker** (`retrieval/reranker/`): two-stage retrieve-then-rerank. `retrieval/reranked.py:RerankedRetriever` wraps any base retriever, fetches `RERANKER_CANDIDATE_K` candidates, reorders to `TOP_K`. Default `RERANKER=claude` — a single Haiku listwise call (`reranker/adapters/claude.py`) returns reordered chunk indices. Phase 5 eval comparison: claude rerank moved retrieval_recall 0.734 → 0.906 and refusal_correctness 0.773 → 0.944. Cross-encoder (BGE-base) was tested and *regressed* — do not assume reranking is automatic improvement.
- **generation** (`generation/adapters/anthropic.py`): streams via `client.messages.stream`. Two prompt templates: `prompts/system.j2` (stable, cached) and `prompts/answer.j2` (per-request, NOT cached). Citations and grounding enforcement run **post-stream**.
- **api** (`api/`): FastAPI app with SSE chat endpoint, CORS pinned to `ALLOWED_ORIGIN`, per-IP token-bucket rate limiter, request-id middleware, bearer auth.

### Prompt caching (load-bearing)

`AnthropicLLM` passes `system` as a list of content blocks with `"cache_control": {"type": "ephemeral"}` on the system text block. Anthropic's minimum cacheable prefix for Haiku 4.5 is ~4096 tokens — `prompts/system.j2` is intentionally ≥~4300 tokens of substantive content (rules, exemplars, pitfalls) to clear that threshold. **Do not shrink `system.j2` below ~4300 tokens** or caching will silently stop firing (`cache_creation_input_tokens` and `cache_read_input_tokens` will both go to 0). Per-request grounding chunks must stay in the user message (`answer.j2`), not in the system block.

Cached-prefix and cache-write/read tokens are priced separately in `config.PRICE_CACHE_*` and tracked in `LLMUsage` (`cache_read_input_tokens`, `cache_creation_input_tokens`).

### Grounding contract

`generation/grounding.py:enforce_grounding` post-processes the final streamed answer: if no `[chunk_id]` citation tokens appear, it forces a refusal with `refusal_reason="out_of_corpus"`. `generation/citations.py` extracts citations with regex `\[([^\[\]\s][^\[\]]*?)\]` and resolves them against the retrieved chunks. This is the only thing standing between the LLM and silent hallucination — preserve the post-hoc check even if the model is instructed to cite.

### Budget / cost

`api/budget.py:BudgetTracker` is a process-wide singleton with a UTC-midnight reset. Each request computes cost from `LLMUsage` (including separate cache read/write buckets) and increments `_spent_today_usd`. When the cap trips, the chat endpoint emits a single SSE `error` event with `code: BUDGET_EXCEEDED` and `retry_after` (seconds until midnight UTC) and terminates. The verification script in `scripts/verify_phase1.py` exercises this by lowering `daily_cap_usd` and preloading `_spent_today_usd`.

### SSE contract

`api/routes/chat.py` emits events in this order: `meta` → `token`* → `citation`* (live-detected from the streamed text) → `done` (with `refused`, `refusal_reason`, `tokens_in`, `tokens_out`, `cost_usd`). Error paths emit a terminal `error` event (`BUDGET_EXCEEDED`, `UPSTREAM_ERROR`). SSE frames use `\r\n\r\n` separators — when parsing in tests, normalize via `body.replace("\r\n", "\n")` before splitting on `\n\n`.

### State

`api/state.py:AppState` lazy-loads the retriever (re-ingests on first request) and LLM as singletons; tests inject a `FakeLLM` via `tests/conftest.py` to avoid spending. Don't instantiate `AnthropicLLM` directly from tests.

## Guardrails (from docs/HANDOFF.md)

Stop and ask before:
- choosing tech not already locked (the locked stack is FastAPI + Anthropic + in-memory store + stub embedder)
- calling Anthropic without `cache_control` on the system block or without a finite `max_tokens`
- adding features beyond the Phase 1 checklist

## Config

`config.py` (pydantic-settings, reads `.env`): `ANTHROPIC_API_KEY`, `LLM_MODEL`, `LLM_MAX_OUTPUT_TOKENS` (must be > 0), `DAILY_BUDGET_USD`, `TOP_K`, `CHUNK_SIZE`, `ALLOWED_ORIGIN`, `API_KEY`, `SAMPLES_DIR`. Anthropic price constants for Haiku 4.5 live here: `PRICE_INPUT_PER_MTOK`, `PRICE_OUTPUT_PER_MTOK`, `PRICE_CACHE_WRITE_PER_MTOK`, `PRICE_CACHE_READ_PER_MTOK`.

## CI

`.github/workflows/ci.yml`: lint + tests on every push to `dev`. The smoke eval job (which hits the real API) is gated by the `run-eval` PR label so it doesn't run for free on every push.
