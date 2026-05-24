# Portfolio integration handover

This file is the bridge between the TwinMind backend repo and your portfolio repo (`chingenlin/portfolio`). It contains:

1. **A paste-ready prompt** to start a fresh Claude Code session in the portfolio repo and have Claude do the integration with full context.
2. **A human checklist** in case you want to do it yourself.

The widget code itself is in this same directory (`portfolio-widget/`).

---

## Option A: paste this prompt into a Claude Code session in `chingenlin/portfolio`

Open the portfolio repo in your editor, launch Claude Code, and paste the prompt below verbatim. It's self-contained — assumes Claude has no prior context about TwinMind.

```
I'm integrating a RAG chatbot backend called TwinMind into this portfolio site.
The backend is already deployed and working. Your job is to wire up the chat widget.

# Context

- Portfolio framework: Vite + React, hosted on Vercel.
- TwinMind backend: deployed on Google Cloud Run, exposes POST /v1/chat as SSE.
- Architecture: browser → fetch('/api/chat') same-origin → Vercel Edge proxy
  (attaches bearer server-side) → Cloud Run → SSE response forwarded back.
- The bearer NEVER reaches client JavaScript. The Edge proxy is what holds it.

# Source files to copy

The TwinMind repo at https://github.com/ChingEnLin/TwinMind contains a
self-contained deliverable under `portfolio-widget/`. These files need to be
copied into this portfolio repo at the SAME paths:

  portfolio-widget/api/chat.ts
    → THIS REPO at: api/chat.ts
    (Vercel auto-detects top-level api/ directory)

  portfolio-widget/src/components/ChatbotWidget/ChatbotWidget.tsx
    → THIS REPO at: src/components/ChatbotWidget/ChatbotWidget.tsx

  portfolio-widget/src/components/ChatbotWidget/parseSSE.ts
    → THIS REPO at: src/components/ChatbotWidget/parseSSE.ts

  portfolio-widget/src/components/ChatbotWidget/ChatbotWidget.module.css
    → THIS REPO at: src/components/ChatbotWidget/ChatbotWidget.module.css

To get these files, you have two options:
  (a) clone the TwinMind repo somewhere and copy the four files
  (b) ask me for each file's content and I'll paste it (it's ~250 lines total)

# What each file does

  api/chat.ts (~60 lines, Vercel Edge runtime):
    Same-origin proxy. Reads TWINMIND_API_BASE and TWINMIND_API_KEY from
    env vars. Forwards POST body to Cloud Run with Authorization header
    attached. Streams the SSE response straight back. Must use
    `export const config = { runtime: "edge" }` — Vercel Node serverless
    buffers responses and would defeat SSE.

  ChatbotWidget.tsx (~180 lines):
    React component. Renders input + transcript. On submit, POSTs to
    /api/chat with { message }. Parses SSE events (meta/token/citation/
    done/error) via parseSSE. Renders citations as numbered footnotes
    [1], [2], ... in the answer body with a citation list below.
    Handles refused answers and error events.

  parseSSE.ts (~60 lines):
    Spec-correct SSE parser. CRLF-tolerant. AsyncGenerator-based. Returns
    { type, data } objects where data is already JSON.parsed.

  ChatbotWidget.module.css:
    Minimal default styles. Almost certainly needs to be replaced or
    overridden to match the portfolio's design system.

# Vercel environment variables to set

Go to the Vercel project settings → Environment Variables. Add to BOTH
"Production" and "Preview":

  TWINMIND_API_BASE = https://twinmind-zbvf2vk22q-uc.a.run.app
  TWINMIND_API_KEY  = (ask me — it's stored in GCP Secret Manager under
                       `twinmind-api-key`. I can fetch it with:
                       `gcloud secrets versions access latest --secret=twinmind-api-key --project=twinmind-497309`)

These MUST NOT be prefixed with VITE_ — that would expose them to client JS.
Plain server-side env names (no prefix) only.

# After files are in place

1. Render the widget somewhere on the portfolio. The simplest test:

   ```tsx
   import { ChatbotWidget } from './components/ChatbotWidget/ChatbotWidget';

   export function SomePage() {
     return (
       <div>
         <h1>Chat with my digital twin</h1>
         <ChatbotWidget />
       </div>
     );
   }
   ```

2. Run the dev server. Try a question like "What did Ching-En do at
   Virtonomy?". Expected behavior:

   - You see tokens stream in as they arrive (not buffered to the end)
   - Citations appear inline as numbered footnotes [1], [2]
   - Citation list at the bottom of the assistant message
   - "Stop" button while streaming, "Send" button when idle

3. If you see CORS errors, the backend's ALLOWED_ORIGIN doesn't include
   your dev/preview URL yet. Tell me — I need to update the Terraform
   tfvars and reapply.

4. If you see 401 from /api/chat — the bearer in Vercel doesn't match
   the backend's API_KEY secret. Re-fetch from Secret Manager and update
   Vercel env vars.

5. If the bearer leaks somehow into client JS (it shouldn't with the
   Edge proxy setup), STOP and tell me immediately.

# Things to ask me about, not infer

- The current ALLOWED_ORIGIN value (whatever I put in the Terraform tfvars
  initially). The widget won't work from a Vercel preview URL if that
  preview URL isn't in the list.
- The CSS — I want to integrate the widget's look with the rest of the
  portfolio, not just paste it in with default styles.
- Where on the portfolio site the chat should live (homepage, dedicated
  /chat page, a floating button, an inline embed, etc).

# Reference docs (if useful)

The TwinMind backend repo has:
  docs/API.md           — wire format, SSE event shapes, error codes
  portfolio-widget/README.md — file-by-file integration notes

You can read those if I haven't given you enough context, but they're
not strictly required for this integration.

# Start by

1. Asking me where I want to place the chat widget on the portfolio
2. Asking me for the four widget source files (or for me to clone the
   TwinMind repo somewhere so you can copy them)
3. Confirming the Vercel env vars are set before we test
```

---

## Option B: do it yourself, no Claude

The actual mechanical steps:

### 1. Copy the four files

From `<TwinMind repo>/portfolio-widget/` to your portfolio repo:

| From | To |
|---|---|
| `api/chat.ts` | `api/chat.ts` (top-level — Vercel auto-detects) |
| `src/components/ChatbotWidget/ChatbotWidget.tsx` | same path |
| `src/components/ChatbotWidget/parseSSE.ts` | same path |
| `src/components/ChatbotWidget/ChatbotWidget.module.css` | same path |

### 2. Set Vercel env vars

Settings → Environment Variables → add for Production AND Preview:

| Name | Value |
|---|---|
| `TWINMIND_API_BASE` | `https://twinmind-zbvf2vk22q-uc.a.run.app` |
| `TWINMIND_API_KEY` | Fetch with `gcloud secrets versions access latest --secret=twinmind-api-key --project=twinmind-497309` |

**Important:** no `VITE_` prefix. These are server-side only — the Edge function reads them, the browser never sees them.

### 3. Render the widget

```tsx
import { ChatbotWidget } from './components/ChatbotWidget/ChatbotWidget';

<ChatbotWidget />
```

### 4. Update the backend's CORS

In the TwinMind repo, edit `terraform/terraform.tfvars`:

```hcl
allowed_origin = "https://your-portfolio.vercel.app,https://chingenlin.com"
```

Then in `terraform/`:

```bash
terraform apply
gh workflow run deploy.yml --ref dev  # picks up the new ALLOWED_ORIGIN
```

### 5. Deploy the portfolio and smoke-test

Push to your portfolio's main branch (or whatever triggers Vercel deploy). Open the deployed site and ask the chatbot a question. Verify:

- [ ] Tokens stream in (not all at once at the end)
- [ ] Citations render as numbered footnotes
- [ ] Citation list appears below the assistant message
- [ ] "Stop" works during streaming
- [ ] No CORS errors in the browser console
- [ ] No 401s in the Network tab
- [ ] The bearer is NOT visible in any client-side fetch (only `/api/chat` shows up; that's same-origin)

### 6. Watch the budget

Cloud Run cost is bounded by the daily Anthropic spend cap (`DAILY_BUDGET_USD`, currently $0.50). If the cap trips, the SSE response will be a single `error` event with code `BUDGET_EXCEEDED` and `retry_after` set to seconds until UTC midnight. The widget renders this inline; users will see something like:

> [BUDGET_EXCEEDED] Daily spend cap reached. Try again tomorrow.

Bump `daily_budget_usd` in tfvars and reapply if you want a higher cap.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| 401 on `/api/chat` from browser | Vercel env vars not set, or wrong runtime | Verify both `TWINMIND_API_BASE` and `TWINMIND_API_KEY` are in Vercel env. Check the Edge function logs in Vercel. |
| 403 from Cloud Run when proxied | Backend rejecting bearer | The `TWINMIND_API_KEY` in Vercel doesn't match `api_key` in tfvars. Re-fetch from Secret Manager. |
| CORS error in browser | Backend's `ALLOWED_ORIGIN` doesn't include Vercel domain | Update tfvars, redeploy backend. |
| Tokens all arrive at once at the end | Vercel API function isn't using Edge runtime | Check `api/chat.ts` has `export const config = { runtime: "edge" }`. |
| `EventSource` doesn't work | `EventSource` doesn't support custom headers | Use `fetch` instead — that's what `ChatbotWidget.tsx` does. |
| Citations are `[invented_id_xyz]` literal in text | Backend's grounding check failed | This shouldn't happen — `enforce_grounding` forces refusal if no citation resolves. If you see it, file a bug. |
