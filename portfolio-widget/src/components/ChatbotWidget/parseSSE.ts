/**
 * Minimal Server-Sent Events parser for the browser side of TwinMind.
 *
 * The backend emits frames like:
 *
 *     event: token\r\n
 *     data: {"text":"hello"}\r\n
 *     \r\n
 *
 * Frames are CRLF-delimited (per the SSE spec) and separated by a blank line.
 * This parser tolerates LF-only servers too — we normalize CRLF to LF before
 * splitting.
 *
 * Usage:
 *   for await (const event of parseSSE(response.body!)) {
 *     // event.type is one of "meta" | "token" | "citation" | "done" | "error"
 *     // event.data is the already-JSON-parsed payload
 *   }
 */

export interface SSEEvent {
  type: string;
  data: unknown;
}

export async function* parseSSE(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<SSEEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      // Normalize CRLF -> LF so we only ever split on \n\n.
      buffer = buffer.replace(/\r\n/g, "\n");

      // Pull off complete frames; keep the trailing partial in the buffer.
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);

        const event = parseFrame(frame);
        if (event) yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function parseFrame(frame: string): SSEEvent | null {
  let eventType = "message";
  const dataLines: string[] = [];

  for (const line of frame.split("\n")) {
    if (!line || line.startsWith(":")) continue; // empty or SSE comment
    const colon = line.indexOf(":");
    if (colon === -1) continue;
    const field = line.slice(0, colon);
    // Per spec: a single space after the colon is stripped if present.
    const value = line.slice(colon + 1).replace(/^ /, "");

    if (field === "event") eventType = value;
    else if (field === "data") dataLines.push(value);
  }

  if (dataLines.length === 0) return null;

  const raw = dataLines.join("\n");
  try {
    return { type: eventType, data: JSON.parse(raw) };
  } catch {
    // Malformed JSON in a data frame — pass through as a string payload
    // rather than crashing the consumer.
    return { type: eventType, data: raw };
  }
}
