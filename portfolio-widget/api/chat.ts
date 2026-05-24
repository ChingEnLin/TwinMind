/**
 * Vercel Edge Function: /api/chat
 *
 * Same-origin proxy from the portfolio browser to the TwinMind backend on
 * Cloud Run. The static bearer token lives only in Vercel env vars; the
 * browser never sees it.
 *
 * Why Edge runtime: Vercel's Node serverless functions buffer responses by
 * default, which would defeat SSE. Edge functions stream natively and use
 * standard web Request/Response, which is what TwinMind already speaks.
 *
 * Required Vercel environment variables (Project Settings → Environment):
 *   - TWINMIND_API_BASE    e.g. https://twinmind-abc123-uc.a.run.app
 *   - TWINMIND_API_KEY     same value as the backend's API_KEY secret
 *
 * Set them for both `production` and `preview` so PR deploys work too.
 */

export const config = {
  runtime: "edge",
};

export default async function handler(req: Request): Promise<Response> {
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "method not allowed" }), {
      status: 405,
      headers: { "content-type": "application/json" },
    });
  }

  const apiBase = process.env.TWINMIND_API_BASE;
  const apiKey = process.env.TWINMIND_API_KEY;
  if (!apiBase || !apiKey) {
    return new Response(
      JSON.stringify({ error: "backend not configured" }),
      { status: 500, headers: { "content-type": "application/json" } }
    );
  }

  // Forward the body verbatim — the backend already validates `message`
  // length and the `session_id` shape per API_CONTRACT.md.
  const upstream = await fetch(`${apiBase}/v1/chat`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${apiKey}`,
    },
    body: req.body,
    // @ts-expect-error: duplex is required when sending a streaming body but
    // isn't in the public TS types yet (Cloudflare/Vercel both honor it).
    duplex: "half",
  });

  // Pass the SSE stream through. Strip hop-by-hop headers that browsers
  // don't need; preserve content-type so the EventSource semantics carry.
  const headers = new Headers();
  headers.set(
    "content-type",
    upstream.headers.get("content-type") ?? "text/event-stream"
  );
  headers.set("cache-control", "no-cache, no-transform");
  headers.set("connection", "keep-alive");

  return new Response(upstream.body, {
    status: upstream.status,
    headers,
  });
}
