from collections.abc import Iterable

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


def chunk_documents(docs: Iterable[Document]) -> list[Chunk]:
    out: list[Chunk] = []
    for doc in docs:
        out.extend(paragraph_chunks(doc))
    return out
