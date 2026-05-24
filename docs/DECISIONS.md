# Design Decisions

A reference for "why is it built this way?" — paired choices and tradeoffs, with what we considered and what evidence drove the call. For the chronological "what I learned along the way" version, see `notes/` (which is gitignored; ask if you want access).

## 1. LLM choice: Haiku 4.5 throughout

**Chosen:** `claude-haiku-4-5-20251001` for production answers, eval judging, and reranking.

**Alternatives considered:**
- Sonnet for answers, Haiku for judge: rejected because Haiku's quality on grounded RAG is sufficient and Sonnet costs 4x more.
- GPT-4o-mini: comparable cost, but prompt-caching parity required some adapter rework. Sticking with one provider for now.

**Why:** Cheapest current Anthropic model with full prompt-caching support. The per-query cost (~$0.005-0.015) keeps us inside the $0.50 daily cap at the traffic levels a personal portfolio actually sees.

**Where it could change:** If we ever add a second LLM (e.g., a stronger judge), the `generation/factory.py` and `eval/metrics/groundedness.py` adapter pattern makes it a one-line swap.

## 2. Embeddings: BGE-small over OpenAI / Voyage

**Chosen:** `BAAI/bge-small-en-v1.5` (384-dim, local) as the production embedder.

**Alternatives considered:**
- OpenAI `text-embedding-3-small`: paid API call per query, adds latency on cold start. Quality on this corpus is comparable.
- Voyage: stronger quality, but adds another provider relationship.
- Local larger model (`bge-large`): better quality but slower and ~1GB extra in the image.

**Why:** Free, CPU-runnable, no extra provider relationship, model fits in memory comfortably. Quality on this corpus (technical English markdown) is more than enough — see `notes/03-why-your-embedder-needs-a-magic-word.md` for the asymmetric-query-prefix discovery that boosted retrieval quality without changing the model.

**Where it could change:** If retrieval recall starts being the bottleneck (currently at 0.906 with reranker), bumping to `bge-large` or moving to a paid embedder would be the next lever.

## 3. Vector store: Chroma persistent, baked into the image

**Chosen:** Chroma's persistent client with the index stored on local disk inside the container.

**Alternatives considered:**
- Managed vector DB (Pinecone, Weaviate Cloud, Qdrant Cloud): operational overhead and recurring cost for no quality gain at this corpus size.
- pgvector: introduces Postgres as a runtime dep; overkill.
- In-memory only (Phase 1 stub): no persistence between restarts; only used for tests now.

**Why:** The corpus is small (~100-200 chunks). Cosine over 100 vectors is a few microseconds. Chroma persistent is "a SQLite file on disk" — no operational story beyond the image itself.

**Tradeoff:** Content changes require a redeploy (the index is rebuilt at image-build time). For a portfolio bot, the update frequency is low enough that this is fine. See `DEPLOYMENT.md` § "Updating content without redeploying code" for what we'd do if this stops being fine.

## 4. Retrieval: Hybrid (vector + BM25) fused with RRF

**Chosen:** Vector retrieval AND BM25 retrieval, fused via Reciprocal Rank Fusion (`k=60`), top 20 candidates kept.

**Alternatives considered:**
- Vector only: weaker on questions with specific technical keywords (where BM25 wins).
- BM25 only: weaker on paraphrased / conceptual queries (where vector wins).
- Weighted sum of normalized scores: requires picking a weight; sensitive to score distribution.

**Why:** RRF only needs ranks, not raw scores. Vector cosine and BM25 produce scores on incompatible scales; rank-based fusion sidesteps normalization. The constant `k=60` is lifted directly from the original 2009 RRF paper and works well in practice. See `notes/05-hybrid-and-the-rank-fusion-trick.md`.

**Evidence:** Hybrid hit 0.734 retrieval_recall@K on the 50-case set before reranking. Vector-only was lower (didn't formally measure post-Phase 3 but ablation in Phase 3 development showed it).

## 5. Reranker: Claude listwise, not cross-encoder

**Chosen:** A single Haiku call per query, listwise — Haiku reorders the top 20 candidates by returning a JSON array of indices.

**Alternatives considered:**
- **BGE cross-encoder** (`bge-reranker-base`, the industry default): **regressed** retrieval_recall from 0.734 → 0.625 on this corpus.
- BGE cross-encoder v2-m3 (larger): not tested; ~568M params vs Haiku call cost — at that size the cost-quality tradeoff is closer to Haiku's territory anyway.
- Pointwise LLM (one call per candidate): N calls × per-call overhead. Listwise is one call.
- No reranker: 42/50 pass rate baseline.

**Why:** The cross-encoder bake-off was the single most informative result of the project — see `notes/10-the-reranker-that-made-things-worse.md`. The "obvious default" tool ranked correct sources lower, likely because:
1. `bge-reranker-base` (280M params) is too small for the technical-English-markdown domain.
2. The corpus contains "shadow" sources (private/lin-profile/* mirrors of public content) that the cross-encoder favored on surface features.
3. Hybrid RRF was already producing a decent candidate pool, so the reranker's upside ceiling was modest while its downside (a model that disagrees with the right answer) was full.

**Evidence:**

| Config | Pass rate | retrieval_recall@K |
|---|---|---|
| no reranker | 42/50 | 0.734 |
| BGE cross-encoder base | 39/50 | 0.625 (regressed) |
| Claude listwise | **48/50** | **0.906** |

**Cost:** ~$0.001-0.003 per query for the rerank call, on top of the answer call. Daily budget cap absorbs the overhead.

**Tradeoff acknowledged:** This couples retrieval quality to API uptime in a way cross-encoders don't. If Anthropic's API has an incident, retrieval still works but rerank falls back to "first 4 of 20" — quality regresses to roughly the no-reranker baseline.

## 6. Prompt caching: system prompt sized to clear the 4096-token threshold

**Chosen:** `prompts/system.j2` is ~4300 tokens of substantive content (rules + 18 worked examples + tone/pitfall sections), sent with `cache_control: ephemeral`.

**Alternatives considered:**
- Short system prompt: doesn't clear Haiku 4.5's ~4096-token minimum for caching, silently pays full price on every request.
- Cache the per-query chunks: invalidates on every query (chunks change); no benefit.
- No caching: simpler, but pays 1.0x input cost for ~2000+ static tokens of system prompt on every query, forever.

**Why:** ~90% discount on cached-read tokens. At ~30k requests/year this is the difference between $X and $X/10 on the input-token line item.

**Risk:** Shrinking `system.j2` below the threshold breaks caching *silently*. The `LLMUsage.cache_creation_input_tokens` + `cache_read_input_tokens` going to zero is the only signal. CLAUDE.md and architecture docs flag this explicitly. See `notes/02-the-4096-token-caching-threshold.md`.

## 7. Grounding contract: refusal is the default, citations are required

**Chosen:** Post-stream, we enforce:
1. The answer must contain at least one `[chunk_id]` token, OR be a refusal.
2. At least one cited ID must resolve to a real retrieved chunk (no invented IDs).
3. Refusals are classified by reason (`out_of_corpus` vs `ambiguous_query`) via phrase detection.

**Alternatives considered:**
- Trust the model to refuse correctly: doesn't survive a single jailbreak attempt.
- Use Anthropic's tool-use schema to force structured citations: heavier, locks us in, doesn't catch invented chunk IDs that *look* well-formed.
- Have a separate "verifier" LLM call: 2x the cost, often disagrees with the answerer in ways that aren't actionable.

**Why:** Post-hoc regex + set lookup is cheap (~microseconds), deterministic, and catches every failure mode we care about. It's the load-bearing safety check between "the LLM said something" and "the user sees something."

**Evidence:** Adversarial category (5 cases including prompt injection, jailbreaks) stays at 5/5 across every pipeline change. The grounding check is what catches "you got past the system prompt, but you can't make up sources."

**Where it's brittle:** The phrase detection for `ambiguous_query` is a heuristic, not a classifier. A model phrasing a refusal in an unexpected way (e.g., a new locale or a different model with different conventions) could miss the classification — but the binary refusal/answer decision would still be correct.

## 8. Eval harness: data / metric / reporting separation

**Chosen:** `EvalRunner` writes observations only (`EvalResult` dataclass with retrieved, citations, refused, etc.). Metrics are pure functions over `EvalResult`. Reporting aggregates metrics for the CLI / PR comment.

**Alternatives considered:**
- `run_case() → PASS/FAIL`: every metric change requires re-running cases. Hostile to iteration.
- Metrics embedded in the runner: same problem; metric changes need re-runs.

**Why:** Lets us add a new metric without re-running 50 cases. Lets us re-score yesterday's run with today's metric definition. Lets us debug a single failure without spinning up the whole eval. See `notes/09-data-metric-reporting-layers.md` for the long-form.

**Known leak:** `EvalResult` still has a `passed` field, which is *interpretation* (yes/no judgment) leaking into the data-layer dataclass. It's there because the smoke-eval workflow predated metrics. Marked for refactor; currently sufficient.

## 9. Hosting: Cloud Run

**Chosen:** Google Cloud Run, scale-to-zero default, Docker image baked with index.

**Alternatives considered:**
- Fly.io (~$5/mo for always-warm), Render (free tier has 30s cold starts), Vercel (no SSE on Hobby; no Python on Edge), AWS Lambda + API Gateway (SSE is painful).

**Why:** Free tier covers more traffic than the portfolio will see, native SSE, container-native (fits the image-is-the-snapshot model), and stays within GCP for everything else (Secret Manager, AR, GCS for content).

**Tradeoff:** Cold starts ~5-8s on a fresh container. Acceptable for a portfolio chatbot where conversations are bursty (first message slow, rest fast). Upgrade path is `min_instances = 1` for ~$5/mo always-warm.

## 10. IaC: Terraform, not Pulumi or hand-managed

**Chosen:** Terraform with the official `google` provider.

**Alternatives considered:**
- Pulumi: more expressive (Python/TS instead of HCL) but smaller community, less Vercel/portfolio-side reusability.
- OpenTofu: identical syntax, an option if HashiCorp licensing becomes a concern.
- gcloud CLI scripts: not IaC; loses the "Terraform is the source of truth for infra" property.

**Why:** Standard tool, mature provider, well-documented. The infra surface is small enough (one service, one bucket, three secrets, two SAs, a WIF pool) that HCL's clunkier syntax isn't a real cost.

## 11. CI auth: Workload Identity Federation, not service-account JSON

**Chosen:** WIF in `terraform/wif.tf` — GitHub Actions OIDC exchanges for a short-lived access token impersonating the deploy SA.

**Alternatives considered:**
- JSON key in GitHub Secrets: long-lived credential in CI, rotation is manual, can leak via accidental log spillage.
- GitHub App with deploy keys: extra moving parts, doesn't replace the GCP-side auth question.

**Why:** No long-lived secrets in CI. Tokens are 1-hour, scoped to the deploy SA. The provider's `attribute_condition` pins issuance to `assertion.repository == "ChingEnLin/TwinMind"`, so even if the WIF pool were enumerated, only this repo can mint tokens.

**Setup gotcha:** WIF needs both `roles/iam.workloadIdentityUser` (for OIDC handshake) AND `roles/iam.serviceAccountTokenCreator` (for `iam.serviceAccounts.getAccessToken`, which subprocess CLIs like gcloud and docker use). The handshake-only role makes OIDC succeed but every actual API call returns `PERMISSION_DENIED`. Both are granted in `wif.tf`.

## 12. Content storage: GCS bucket, build-time sync

**Chosen:** Private GCS bucket holds the gitignored `private/` subtree. CI does `gcloud storage rsync` into the build context *before* `docker build`, so the Dockerfile stays simple (just reads from `data/`).

**Alternatives considered:**
- Private GitHub repo: simpler auth (PAT) but adds a second repo to maintain.
- Drive (markdown files OR Docs): more setup complexity, conversion edge cases for Docs.
- Drive with a service account: works but the share-folder-with-SA dance is more setup than GCS.
- Runtime fetch from GCS at startup: adds ~30s to cold start; not worth it for a portfolio.

**Why:** Single source of truth for content, same auth flow as everything else (WIF for CI, gcloud for the human). Effectively free at this volume (well inside 5GB free tier).

**Why not in the Dockerfile:** The sync runs in the workflow, not the Dockerfile. Two reasons: (1) the build needs no GCP credentials, making it portable to any machine; (2) local dev (`docker build .`) just uses the local filesystem with no GCS round-trip. See `DEPLOYMENT.md` § "Why split build-time content sync from the Dockerfile".

## 13. Portfolio auth: static bearer via Vercel edge proxy

**Chosen:** A static API key, stored in Vercel env vars and attached server-side by the Edge function in `portfolio-widget/api/chat.ts`. Browser only sees same-origin `/api/chat`.

**Alternatives considered:**
- Signed short-lived JWT (5-min lifetime, HMAC-signed by Vercel function, verified by backend): more secure if a token leaks, but adds a verification middleware on the backend and a rotation story for the shared secret.
- Cloud Run IAM auth via service account: most production-grade. Requires SA token minting from Vercel (more setup).
- No auth, public endpoint: dangerous (abuse + cost).

**Why:** For a personal portfolio's traffic, the static bearer is sufficient and the simplest to ship. The bearer never reaches client JS (lives only in Vercel env vars, attached server-side). Rotation is one Terraform variable change + Vercel env var update.

**Upgrade path:** If abuse becomes a problem, swap to signed JWTs without changing the API surface — the backend would add a verification step and the Vercel function would mint instead of attach.

## 14. SSE over JSON polling / streamed JSON / WebSockets

**Chosen:** Server-Sent Events with explicit event types (`meta`, `token`, `citation`, `done`, `error`).

**Alternatives considered:**
- WebSockets: bidirectional, but we don't need bidirectional, and they're harder to debug.
- One big JSON response at the end: no streaming = bad UX for chat (perceived latency).
- Newline-delimited JSON: works, but lacks event types, harder for clients to dispatch.
- Anthropic's native streaming format passthrough: locks the contract to Anthropic's event shape.

**Why:** SSE is the right tool for "server pushes a sequence of events to one client." The browser's `EventSource` API doesn't support custom headers (no bearer), so the widget uses `fetch` with manual parsing — but the wire format is still SSE-compliant. The explicit event types let the client dispatch cleanly without parsing the payload.

## 15. Prompt-loosening over rule-adding

**Chosen:** When the model over-refuses, soften the existing rule that's pushing the binary "refuse or fully answer" framing. Don't add new rules.

**Alternatives considered:**
- Add a rule "you may answer partially when appropriate": competes with the existing absolute-toned rules; model averages tones.
- Train a fine-tuned model: way out of scope, also doesn't address the prompt-design lesson.
- Lower the refusal-detection bar: the bar isn't the problem; the model's interpretation of the prompt is.

**Why:** Phase 5's prompt-loosening moved `refusal_correctness` from 0.708 → 0.773 by softening Rule 4 + the "either-or" tone in the prompt's tone section. Three new examples (enumeration, "how experienced" → demonstrated work, cross-source synthesis) helped concrete it. Safety stayed perfect (refusal-corpus 10/10, adversarial 5/5). See `notes/11-prompts-as-behavior-shapers.md`.

**Lesson:** Prompts are tone-setters more than rule-lists. When you want behavior to change, edit the rule that's producing the current behavior, not the rule that describes the new behavior. Usually those are the same rule reworded.
