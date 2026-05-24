# TwinMind portfolio widget

These files are the deliverable for the `chingenlin/portfolio` repo. They're checked into this repo as a versioned reference so that future updates to the wire format / SSE event shape can land here first and then be propagated.

## Files

| File | Where it goes in the portfolio repo |
|---|---|
| `api/chat.ts` | `api/chat.ts` (top-level — Vercel auto-detects it) |
| `src/components/ChatbotWidget/ChatbotWidget.tsx` | same path |
| `src/components/ChatbotWidget/parseSSE.ts` | same path |
| `src/components/ChatbotWidget/ChatbotWidget.module.css` | same path |

## Integration

1. **Copy the files** into the portfolio repo at the paths above.

2. **Set Vercel env vars** (Project Settings → Environment Variables — set for `Production` and `Preview`):
   - `TWINMIND_API_BASE` = the Cloud Run service URL (e.g. `https://twinmind-abc123-uc.a.run.app`)
   - `TWINMIND_API_KEY` = the same value you put into the backend's `api_key` Terraform variable

3. **Render the component** somewhere in the portfolio:
   ```tsx
   import { ChatbotWidget } from './components/ChatbotWidget/ChatbotWidget';

   <ChatbotWidget />
   ```

4. **Deploy the portfolio** — Vercel picks up the `api/` directory automatically. Visit `https://<your-vercel-domain>/api/chat` after deploy and it should return `{"error":"method not allowed"}` on GET (a sign the function is wired up and reachable).

5. **Update the backend's `ALLOWED_ORIGIN`** Terraform variable to include the portfolio's production URL, then `terraform apply`. (Multiple comma-separated origins are supported — useful for adding preview URLs.)

## How the auth flow works

```
Browser  ──fetch /api/chat──▶  Vercel Edge fn  ──fetch /v1/chat──▶  Cloud Run
   ▲             same-origin         (attaches Bearer)        cross-origin
   │                                  ▲
   │                                  └── TWINMIND_API_KEY (env, not client JS)
   │
   └── SSE stream forwarded through unchanged
```

The static bearer never reaches client JavaScript. The browser doesn't know the backend URL or the key — only the Vercel function does.

## SSE event types the widget handles

Per `docs/API_CONTRACT.md` in the TwinMind repo:

| Event | When | What the widget does |
|---|---|---|
| `meta` | once, before tokens | (ignored in UI; useful for `request_id` debugging) |
| `token` | many | append to current assistant message |
| `citation` | zero or more | dedup by id, add to footnote list, rewrite `[id]` → `[n]` |
| `done` | once | mark as finished; capture `refused` + `refusal_reason` |
| `error` | terminal | render the error code + message inline |

## Styling

`ChatbotWidget.module.css` is intentionally vanilla. Replace it (or override the class names) to match your portfolio's design system.

## Future: conversation memory

The SSE contract supports an optional `session_id` in the request body. Phase 1-6 backend ignores it; when the backend ships memory support (Phase 6+ per HANDOFF), thread a session id through the widget — generate one on mount with `crypto.randomUUID()` and pass it in the `body` of the `fetch('/api/chat', ...)` call.
