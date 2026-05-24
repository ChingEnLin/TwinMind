/**
 * ChatbotWidget — minimal React UI for TwinMind.
 *
 * Talks only to /api/chat on its own origin; the Vercel Edge function in
 * api/chat.ts is what attaches the backend bearer and forwards the SSE
 * stream from Cloud Run.
 *
 * Citations are rendered as numbered footnotes — the SSE `citation` events
 * carry { id, source, section?, url? } per API_CONTRACT.md. We deduplicate
 * by id and assign footnote numbers in first-seen order.
 *
 * Single-turn for now (no session memory). The backend accepts an optional
 * session_id but ignores it in Phase 1; wire it up here when conversation
 * memory ships.
 */

import { useCallback, useMemo, useRef, useState } from "react";
import { parseSSE, type SSEEvent } from "./parseSSE";
import styles from "./ChatbotWidget.module.css";

interface Citation {
  id: string;
  source: string;
  section?: string;
  url?: string | null;
}

interface Message {
  role: "user" | "assistant";
  text: string;
  citations: Citation[];
  refused?: boolean;
  refusalReason?: string | null;
}

export function ChatbotWidget() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const submit = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || streaming) return;

    setError(null);
    setInput("");
    setMessages((prev) => [
      ...prev,
      { role: "user", text: trimmed, citations: [] },
      { role: "assistant", text: "", citations: [] },
    ]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        const detail = await res.text().catch(() => res.statusText);
        throw new Error(`backend returned ${res.status}: ${detail}`);
      }

      const seenCitationIds = new Set<string>();

      for await (const event of parseSSE(res.body)) {
        applyEvent(event, seenCitationIds, setMessages);
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError((err as Error).message);
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, [input, streaming]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  // Auto-scroll to bottom on new content.
  const scrollRef = useRef<HTMLDivElement | null>(null);
  useMemo(() => {
    queueMicrotask(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
    });
  }, [messages]);

  return (
    <div className={styles.widget}>
      <div className={styles.transcript} ref={scrollRef}>
        {messages.length === 0 && (
          <div className={styles.empty}>
            Ask anything about Ching-En's work — experience, projects, technical decisions.
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageView key={i} msg={msg} />
        ))}
        {error && <div className={styles.error}>{error}</div>}
      </div>

      <form
        className={styles.composer}
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <input
          className={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="What did Ching-En do at Virtonomy?"
          disabled={streaming}
          aria-label="Ask a question"
        />
        {streaming ? (
          <button type="button" className={styles.button} onClick={stop}>
            Stop
          </button>
        ) : (
          <button type="submit" className={styles.button} disabled={!input.trim()}>
            Send
          </button>
        )}
      </form>
    </div>
  );
}

function MessageView({ msg }: { msg: Message }) {
  if (msg.role === "user") {
    return <div className={styles.userMessage}>{msg.text}</div>;
  }

  // Render assistant text with [chunk_id] tokens replaced by footnote numbers.
  // The order of msg.citations is the order ids were first seen on the wire,
  // which matches what we want footnote-numbering-wise.
  const idToNumber = new Map<string, number>();
  msg.citations.forEach((c, i) => idToNumber.set(c.id, i + 1));

  const rendered = msg.text.replace(/\[([^\[\]\s][^\[\]]*?)\]/g, (match, id) => {
    const n = idToNumber.get(id as string);
    return n ? `[${n}]` : match;
  });

  return (
    <div className={styles.assistantMessage}>
      <div className={styles.assistantText}>{rendered}</div>
      {msg.citations.length > 0 && (
        <ol className={styles.citationList}>
          {msg.citations.map((c, i) => (
            <li key={c.id} value={i + 1}>
              {c.url ? (
                <a href={c.url} target="_blank" rel="noreferrer">
                  {c.source}
                  {c.section ? ` — ${c.section}` : ""}
                </a>
              ) : (
                <span>
                  {c.source}
                  {c.section ? ` — ${c.section}` : ""}
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function applyEvent(
  event: SSEEvent,
  seenCitationIds: Set<string>,
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
): void {
  // All events mutate the LAST message (the assistant slot we appended).
  setMessages((prev) => {
    if (prev.length === 0) return prev;
    const next = prev.slice();
    const last = { ...next[next.length - 1] };

    switch (event.type) {
      case "token": {
        const text = (event.data as { text?: string })?.text ?? "";
        last.text += text;
        break;
      }
      case "citation": {
        const c = event.data as Citation;
        if (c?.id && !seenCitationIds.has(c.id)) {
          seenCitationIds.add(c.id);
          last.citations = [...last.citations, c];
        }
        break;
      }
      case "done": {
        const d = event.data as { refused?: boolean; refusal_reason?: string };
        last.refused = !!d?.refused;
        last.refusalReason = d?.refusal_reason ?? null;
        break;
      }
      case "error": {
        const d = event.data as { code?: string; message?: string };
        last.text += `\n\n[${d?.code ?? "error"}] ${d?.message ?? "request failed"}`;
        last.refused = true;
        break;
      }
      case "meta":
      default:
        // `meta` carries request_id + retrieved preview; we don't surface it
        // in the UI but the backend includes it for debugging.
        break;
    }

    next[next.length - 1] = last;
    return next;
  });
}
