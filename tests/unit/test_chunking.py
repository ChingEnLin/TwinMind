from twin_mind.chunking.strategies import paragraph_chunks, token_aware_chunks
from twin_mind.models.document import Document, Source


def test_paragraph_chunker_extracts_sections():
    text = "# Title\n\n## Section A\n\nfirst paragraph\nstill first.\n\nsecond paragraph.\n"
    doc = Document(id="x.md", source=Source(name="x.md"), text=text)
    chunks = list(paragraph_chunks(doc))
    assert len(chunks) == 2
    assert chunks[0].section == "Section A"
    assert "first paragraph" in chunks[0].text
    assert "second paragraph" in chunks[1].text


def test_token_aware_packs_small_doc_into_one_chunk():
    text = "# Title\n\n## Section A\n\nshort paragraph.\n\nanother short paragraph.\n"
    doc = Document(id="x.md", source=Source(name="x.md"), text=text)
    chunks = list(token_aware_chunks(doc, target_tokens=400, overlap_tokens=0))
    assert len(chunks) == 1
    assert "short paragraph" in chunks[0].text
    assert "another short paragraph" in chunks[0].text
    assert chunks[0].section == "Section A"


def test_token_aware_splits_when_over_target_and_overlaps():
    # Build paragraphs so each is ~80 tokens (~320 chars). Target 100 → splits.
    para = ("word " * 80).strip()
    text = "\n\n".join([para, para, para])
    doc = Document(id="x.md", source=Source(name="x.md"), text=text)
    chunks = list(token_aware_chunks(doc, target_tokens=100, overlap_tokens=20))
    assert len(chunks) >= 2
    # Overlap: chunk N's tail should appear at the start of chunk N+1.
    tail = chunks[0].text.split()[-5:]
    head = chunks[1].text.split()[:10]
    overlap_hit = any(w in head for w in tail)
    assert overlap_hit, "expected chunk[1] to begin with tail of chunk[0]"


def test_token_aware_strips_leading_headers():
    text = "# Title\n\n## Section A\n\nbody line one.\nbody line two.\n"
    doc = Document(id="x.md", source=Source(name="x.md"), text=text)
    chunks = list(token_aware_chunks(doc, target_tokens=400, overlap_tokens=0))
    assert chunks
    assert not chunks[0].text.lstrip().startswith("#"), (
        f"headers should be stripped from chunk body, got: {chunks[0].text!r}"
    )
