# TwinMind docs

| File | What's in it |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System layout, the protocols/adapters pattern, the data flow in one request, prompt caching, state lifecycle |
| [`API.md`](API.md) | HTTP + SSE wire format, auth, rate limits, error codes, smoke test with curl |
| [`EVAL.md`](EVAL.md) | The eval harness, the four metrics, the golden set, current baseline, how to add cases/metrics |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | Cloud Run + Terraform + GitHub Actions, bootstrap from zero, cost, ops |
| [`DECISIONS.md`](DECISIONS.md) | Key design decisions with alternatives, evidence, and tradeoffs |

For the chronological "what I learned along the way" notes (the surprising-result stories behind some of these decisions), see `notes/` in the repo root. Those are gitignored — local reference, more candid in tone than what's here.

Suggested reading order if you're new:
1. The top-level `README.md` for orientation
2. `ARCHITECTURE.md` to understand the pipeline
3. `API.md` if you're integrating against it
4. `EVAL.md` + `DECISIONS.md` if you want to understand the *why*
5. `DEPLOYMENT.md` if you're operating it
