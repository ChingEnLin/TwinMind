from collections.abc import Iterable

from twin_mind.config import settings
from twin_mind.models.document import Chunk, Document


def _current_section(lines: list[str], idx: int) -> str | None:
    for i in range(idx, -1, -1):
        line = lines[i].strip()
        if line.startswith("#"):
            return line.lstrip("# ").strip() or None
    return None


def paragraph_chunks(doc: Document) -> Iterable[Chunk]:
    lines = doc.text.splitlines()
    paragraphs: list[tuple[str, str | None]] = []
    buf: list[str] = []
    buf_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "":
            if buf:
                section = _current_section(lines, buf_start)
                paragraphs.append(("\n".join(buf).strip(), section))
                buf = []
            buf_start = i + 1
        else:
            if not buf:
                buf_start = i
            buf.append(line)
    if buf:
        paragraphs.append(("\n".join(buf).strip(), _current_section(lines, buf_start)))

    n = 0
    for text, section in paragraphs:
        # Strip leading consecutive header lines; the section name already captures them.
        body_lines = text.splitlines()
        while body_lines and body_lines[0].lstrip().startswith("#"):
            body_lines.pop(0)
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        chunk_id = f"{doc.id}#{n}"
        n += 1
        yield Chunk(
            id=chunk_id,
            doc_id=doc.id,
            source=doc.source,
            text=body,
            section=section,
        )


def _approx_tokens(text: str) -> int:
    """Cheap token estimate without a tokenizer dep: ~4 chars/token for English.

    Good enough to bucket paragraphs into target-sized chunks. We do not need
    exact counts here — the LLM's tokenizer is what bills, not ours.
    """
    return max(1, len(text) // 4)


def _tail_for_overlap(text: str, overlap_tokens: int) -> str:
    """Return the last ~overlap_tokens worth of `text`, sliced on a word boundary."""
    if overlap_tokens <= 0 or not text:
        return ""
    approx_chars = overlap_tokens * 4
    if len(text) <= approx_chars:
        return text
    tail = text[-approx_chars:]
    # back up to the next whitespace so we don't slice mid-word
    space = tail.find(" ")
    if space != -1:
        tail = tail[space + 1 :]
    return tail


def token_aware_chunks(
    doc: Document,
    target_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> Iterable[Chunk]:
    """Greedy paragraph packing with overlap.

    Walk paragraphs in order; pack into the current chunk until adding the next
    one would exceed `target_tokens`. When we emit a chunk, seed the next one
    with the tail (~overlap_tokens) of the previous chunk so a sentence sitting
    on a boundary is still seen in both chunks.

    Header lines (``#``) are stripped from each paragraph's body; the nearest
    preceding ``##``-style header is attached as the chunk's section.
    """
    target = target_tokens or settings.CHUNK_TARGET_TOKENS
    overlap = overlap_tokens if overlap_tokens is not None else settings.CHUNK_OVERLAP_TOKENS

    lines = doc.text.splitlines()
    # First, gather paragraphs with their section context (reuse paragraph logic).
    paragraphs: list[tuple[str, str | None]] = []
    buf: list[str] = []
    buf_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "":
            if buf:
                section = _current_section(lines, buf_start)
                paragraphs.append(("\n".join(buf).strip(), section))
                buf = []
            buf_start = i + 1
        else:
            if not buf:
                buf_start = i
            buf.append(line)
    if buf:
        paragraphs.append(("\n".join(buf).strip(), _current_section(lines, buf_start)))

    # Strip leading header lines from each paragraph body.
    cleaned: list[tuple[str, str | None]] = []
    for text, section in paragraphs:
        body_lines = text.splitlines()
        while body_lines and body_lines[0].lstrip().startswith("#"):
            body_lines.pop(0)
        body = "\n".join(body_lines).strip()
        if body:
            cleaned.append((body, section))

    # Greedy pack with overlap.
    n = 0
    current_text = ""
    current_section: str | None = None
    current_tokens = 0
    for body, section in cleaned:
        body_tokens = _approx_tokens(body)
        # First paragraph in a chunk sets its section.
        if not current_text:
            current_section = section
        # If adding this paragraph would blow the budget, emit and roll over.
        if current_text and current_tokens + body_tokens > target:
            yield Chunk(
                id=f"{doc.id}#{n}",
                doc_id=doc.id,
                source=doc.source,
                text=current_text,
                section=current_section,
            )
            n += 1
            tail = _tail_for_overlap(current_text, overlap)
            current_text = tail
            current_tokens = _approx_tokens(tail) if tail else 0
            current_section = section
        # Append the paragraph.
        if current_text:
            current_text = current_text + "\n\n" + body
        else:
            current_text = body
        current_tokens += body_tokens

    if current_text.strip():
        yield Chunk(
            id=f"{doc.id}#{n}",
            doc_id=doc.id,
            source=doc.source,
            text=current_text,
            section=current_section,
        )


def chunk_documents(docs: Iterable[Document], strategy: str | None = None) -> list[Chunk]:
    strat = strategy or settings.CHUNK_STRATEGY
    out: list[Chunk] = []
    for doc in docs:
        if strat == "token_aware":
            out.extend(token_aware_chunks(doc))
        elif strat == "paragraph":
            out.extend(paragraph_chunks(doc))
        else:
            raise ValueError(f"unknown chunk strategy: {strat}")
    return out
