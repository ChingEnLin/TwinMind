# TwinMind

> A retrieval-augmented "digital twin" chatbot of [Ching-En Lin](https://github.com/ChingEnLin) — strictly grounded answers about his engineering background, with citations and refusals when the corpus doesn't support an answer.

**Live:** `https://twinmind-zbvf2vk22q-uc.a.run.app` (consumed by the chat widget on his portfolio site)

```
┌────────────┐      ┌─────────────┐      ┌──────────────────┐      ┌──────────────┐
│ Portfolio  │ SSE  │ Vercel Edge │ SSE  │  Cloud Run       │ →    │  Anthropic   │
│ (browser)  ├─────▶│ proxy       ├─────▶│  TwinMind API    │      │  Haiku 4.5   │
│ Vite/React │      │ (bearer)    │      │  (FastAPI)       │      └──────────────┘
└────────────┘      └─────────────┘      └──────────────────┘
                                                  │
                                         ┌────────┴─────────┐
                                         │ hybrid retrieval │
                                         │ + Claude rerank  │
                                         │ over Chroma      │
                                         └──────────────────┘
```

## What's interesting about this

This isn't "another RAG chatbot." It's a deliberately small, measurable, production-grade pipeline built phase-by-phase, with the measurement instrument shipped *alongside* the system being measured. Some highlights:

- **Strict grounding.** The model refuses (with reasons) when the retrieved chunks don't support an answer. Every claim is citation-required; a post-hoc check verifies citations resolve to real retrieved chunks before the answer ships.
- **Hybrid retrieval + LLM listwise rerank.** Dense (BGE-small) + sparse (BM25) fused with reciprocal rank fusion, then reordered by Haiku in a single listwise call. Cross-encoders were tested and *underperformed* on this corpus — see `docs/DECISIONS.md`.
- **Per-dimension eval harness.** 50-case golden set scored on four independent metrics (retrieval recall, citation precision, refusal correctness, answer faithfulness). The aggregate pass rate is rarely what you actually want to look at — see `docs/EVAL.md` and `notes/08-observability-as-a-precondition-for-improvement.md`.
- **Cost discipline.** Prompt caching on the static system prompt (intentionally sized to clear the 4096-token cache threshold for Haiku 4.5), strict `max_tokens` on every request, daily-spend circuit breaker that returns SSE `BUDGET_EXCEEDED` and refuses cleanly.
- **Container is the snapshot.** The Docker image bakes the pre-built Chroma index and BGE weights, so cold start is "open file from disk" rather than "build index and download model." Trades image size (~1.5GB) for ~5s cold-start instead of ~60s.

## Current numbers (post-Phase 5, on the 50-case golden set)

| Metric | Score |
|---|---|
| `retrieval_recall@K`     | **0.906** |
| `citation_precision`     | 0.742  |
| `refusal_correctness`    | **0.944** |
| `answer_faithfulness`    | **0.902** (Haiku-as-judge) |
| Pass rate                | 48 / 50 |

The two remaining failures are wrong-source citations to private corpus duplicates — a corpus-dedup issue, not a pipeline issue.

## Quickstart (local dev)

```bash
cp .env.example .env          # set ANTHROPIC_API_KEY at minimum
make install                  # uv sync --extra dev
make ingest                   # build Chroma index from data/samples/
make query Q="What did Ching-En do at Virtonomy?"
make serve                    # FastAPI on :8000

# Test the full pipeline against the real API:
make e2e                      # 10-case smoke eval (costs ~$0.01)

# Per-metric breakdown (costs ~$0.10 with --judge):
uv run tm eval --suite full --judge --report eval_report.md
```

See `Makefile` for all entry points. `pyproject.toml` lists optional dev deps (pytest, ruff, mypy).

## Repository layout

```
src/twin_mind/
  ingestion/        — load source documents (local + GitHub)
  chunking/         — token-aware splitting, ~400 tokens per chunk
  embeddings/       — BGE-small-en-v1.5 (default) or hash-based stub
  vectorstore/      — Chroma persistent (default) or in-memory
  retrieval/        — vector + BM25 + RRF fusion, then reranker wrapper
    reranker/       — identity stub, cross-encoder, Claude listwise (default)
  generation/       — Anthropic adapter, prompt templates, grounding check
    prompts/        — system.j2 (cached), answer.j2 (per-request)
  eval/             — golden set runner + four per-dimension metrics
  api/              — FastAPI app, SSE chat route, middleware, budget
  cli/              — `tm` command (ingest, query, serve, eval)

tests/              — unit tests (70+) and contract tests
eval/golden/        — smoke.yaml (10 cases) and full.yaml (50 cases)
terraform/          — GCP infrastructure (Cloud Run, AR, Secret Manager, WIF)
portfolio-widget/   — deliverable for the portfolio repo (proxy + React)
notes/              — learning notes from each phase (local-only, gitignored)
docs/               — design + ops documentation (this is where to go next)
```

## Documentation

- **`docs/ARCHITECTURE.md`** — system design, layer protocols, adapter pattern, what each piece does
- **`docs/API.md`** — HTTP/SSE wire format, auth, rate limits, error codes
- **`docs/EVAL.md`** — the harness, the four metrics, how to add cases, how to interpret scores
- **`docs/DEPLOYMENT.md`** — Cloud Run + Terraform + GitHub Actions deploy, infra walkthrough, bootstrap
- **`docs/DECISIONS.md`** — key design decisions, what we considered, why we chose what we did

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 | Scaffold: FastAPI + SSE + stub embedder + in-memory store + Haiku w/ prompt caching | ✅ |
| 2 | BGE embedder, persistent Chroma store, token-aware chunking | ✅ |
| 3 | GitHub ingestion + hybrid retrieval (BM25 + vector via RRF) | ✅ |
| 4 | Per-dimension eval as a first-class measurement instrument | ✅ |
| 5 | Reranker layer + grounding hardening | ✅ |
| 6 | API + portfolio integration: Cloud Run + Terraform + GitHub Actions + widget | ✅ |

## Tech choices

| Decision | Choice | Why |
|---|---|---|
| LLM | Claude Haiku 4.5 | Cheapest current Anthropic model with full prompt caching support |
| Embeddings | BGE-small-en-v1.5 (384-dim) | Strong English retrieval, free, runs on CPU |
| Vector store | Chroma (persistent) | Single-process, file-backed, no infra to operate |
| Reranker | Haiku listwise (1 call/query) | Beat BGE cross-encoder by a wide margin on the eval — see DECISIONS.md |
| Hosting | Cloud Run | Scale-to-zero, free-tier-friendly, native SSE support |
| IaC | Terraform | Standard; Workload Identity Federation for CI auth |
| CI/CD | GitHub Actions | WIF auth (no long-lived JSON keys), gcloud-based deploy |

## License

No license attached — this is a personal project. If you want to use parts of it, open an issue.
