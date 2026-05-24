# API

HTTP + Server-Sent Events. One endpoint does the real work (`POST /v1/chat`); everything else is health checks and (deferred) admin.

## Base URL

| Env | URL |
|---|---|
| Prod | `https://twinmind-zbvf2vk22q-uc.a.run.app` |
| Local dev | `http://localhost:8000` |

The portfolio reads it from `TWINMIND_API_BASE` (server-side env var in the Vercel edge proxy, never shipped to client JS).

## Versioning

- Path-prefixed: all endpoints live under `/v1/`.
- Breaking changes bump the prefix (`/v2/`). Non-breaking additions (new event types, optional fields) keep `/v1/`.

## Authentication

All endpoints except `/v1/healthz` require a bearer token:

```
Authorization: Bearer <api-key>
```

The static API key lives in:
- **Backend**: Secret Manager (`twinmind-api-key`), mounted into Cloud Run as env var `API_KEY`
- **Portfolio**: Vercel env var `TWINMIND_API_KEY` (server-side only)

The key never reaches client JS — the Vercel edge proxy attaches it on the wire from server to Cloud Run.

## Endpoints

### `POST /v1/chat`

Stream a grounded answer to a single user question.

**Request body**

```json
{
  "message": "What did Ching-En do at Virtonomy?",
  "session_id": "optional-uuid-for-future-conversation-memory"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `message` | string | yes | 1–500 chars. Longer is rejected with 400. |
| `session_id` | string | no | Reserved for conversation memory. Currently ignored by the backend. |

**Response**

`Content-Type: text/event-stream`

SSE frames are CRLF-delimited (`\r\n\r\n` between frames). The parser in `portfolio-widget/src/components/ChatbotWidget/parseSSE.ts` normalizes to LF before splitting.

Events arrive in this order:

#### 1. `meta` (once, before any tokens)

```
event: meta
data: {"request_id":"req_984356e02d6e","retrieved":[{"id":"experience/virtonomy.md#0","source":"experience/virtonomy.md","section":"Role","score":20.0,"url":null}]}
```

The retrieved chunks are what the LLM was given as context. Useful for debugging "why did it cite this?"

#### 2. `token` (many)

```
event: token
data: {"text":"Ching-En joined Virtonomy in 2023"}
```

Streamed text deltas. Concatenate to form the full answer.

#### 3. `citation` (zero or more, live-detected)

```
event: citation
data: {"id":"experience/virtonomy.md#0","source":"experience/virtonomy.md","section":"Role","url":null}
```

Emitted as the model writes a `[chunk_id]` token in the streamed text, deduplicated by id. The widget renders these as numbered footnotes (`[1]`, `[2]`) in the answer body, with the full list at the bottom.

#### 4. `done` (exactly one, last on success)

```
event: done
data: {"refused":false,"refusal_reason":null,"tokens_in":6744,"tokens_out":134,"cost_usd":0.00875}
```

- `refused: true` means the answer was a refusal (no support, off-topic, ambiguous, etc.). The widget should style differently — e.g., italic, no thumbs-up.
- `refusal_reason` is one of `"out_of_corpus"`, `"ambiguous_query"`, or `null` (when not refused). See `EVAL.md` for the taxonomy.
- `tokens_in` includes cached-read tokens at their full count (pricing is applied separately).
- `cost_usd` is the actual marginal cost of this request, computed from `LLMUsage` with separate cache-read/write rates.

#### 5. `error` (terminal, replaces `done` on failure)

```
event: error
data: {"code":"BUDGET_EXCEEDED","message":"Daily spend cap reached. Try again tomorrow.","retry_after":86400}
```

### `GET /v1/healthz`

Liveness probe. No auth. Returns `200 OK` with `{"status":"ok"}` if the process is up.

```bash
curl https://twinmind-zbvf2vk22q-uc.a.run.app/v1/healthz
# {"status":"ok"}
```

Used by Cloud Run's startup probe (per `terraform/main.tf`) to wait for the container to be ready before routing traffic.

### `POST /v1/admin/reindex` *(not implemented — future)*

Trigger a background reindex without redeploying. Currently content updates require a redeploy because the Chroma index is baked into the image at build time. See `DEPLOYMENT.md` for the rationale.

## Error codes

| Code | HTTP status | Meaning |
|---|---|---|
| `INVALID_REQUEST` | 400 | Malformed body, message too long/empty |
| `UNAUTHORIZED` | 401 | Missing or bad bearer token |
| `RATE_LIMITED` | 429 | Per-IP rate limit hit. `retry_after` in seconds. |
| `BUDGET_EXCEEDED` | 503 | Daily Anthropic spend cap hit. `retry_after` is seconds until UTC midnight. |
| `UPSTREAM_ERROR` | 502 | Anthropic API failure (after the SDK's internal retries) |
| `INTERNAL` | 500 | Unexpected backend error |

**Pre-stream errors** are returned as standard JSON with the matching HTTP status:

```json
{ "error": { "code": "UNAUTHORIZED", "message": "Missing or invalid bearer token" } }
```

**Mid-stream errors** are emitted as `event: error` and the stream closes immediately after.

## Rate limits

Enforced in middleware before any Anthropic call, so rate-limited requests never burn budget.

| Scope | Limit | Mechanism |
|---|---|---|
| Per IP | 10 req / min | Token bucket in process memory |
| Daily spend | `DAILY_BUDGET_USD` (default $0.50) | Running counter, UTC-midnight reset |

Per-IP rate-limit response: `429` with `RATE_LIMITED` error code. Daily-spend cap response: `503` with `BUDGET_EXCEEDED` and `retry_after` set to seconds until UTC midnight.

## CORS

Configured in `src/twin_mind/api/middleware.py`. Origins are read from `ALLOWED_ORIGIN` env var, which supports comma-separated values for multiple origins (production portfolio + Vercel preview URLs):

```
ALLOWED_ORIGIN=https://chingenlin.com,https://chingenlin-preview-abc.vercel.app
```

Methods: `POST, GET, OPTIONS`. Credentials: not required (bearer-token auth, not cookies).

## Smoke test with curl

```bash
API_KEY=$(gcloud secrets versions access latest --secret=twinmind-api-key --project=twinmind-497309)

curl -N -X POST https://twinmind-zbvf2vk22q-uc.a.run.app/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"message":"What did Ching-En do at Virtonomy?"}'
```

The `-N` flag disables curl's buffering so SSE frames appear as they arrive (otherwise you'd see the entire response in one chunk at the end).

## Client-side reference (Vercel edge proxy)

The portfolio's `api/chat.ts` is intentionally minimal — it just forwards the request body to Cloud Run with the bearer attached, and pipes the SSE response straight back to the browser. See `portfolio-widget/api/chat.ts` in the TwinMind repo for the implementation. Key constraints:

- **Use Edge runtime** (`export const config = { runtime: "edge" }`). Vercel Node serverless functions buffer responses by default, which defeats SSE.
- **Forward `req.body` directly** (no JSON.parse + re-stringify). Less work, fewer chances to mangle the request.
- **Don't expose the API base or key to the client.** Both live in Vercel env vars (`TWINMIND_API_BASE`, `TWINMIND_API_KEY`).

## SSE parsing notes

If you write your own client, three gotchas to know:

1. **Use `fetch`, not `EventSource`.** `EventSource` doesn't support custom headers, so you can't attach the bearer.
2. **Normalize CRLF before splitting.** Browser implementations of SSE may produce `\r\n` or `\n` separators; treating them uniformly avoids dropped frames.
3. **Frames are double-newline separated, not double-CRLF.** After normalizing, split on `\n\n`.

See `portfolio-widget/src/components/ChatbotWidget/parseSSE.ts` for a spec-correct minimal parser (~60 lines).
