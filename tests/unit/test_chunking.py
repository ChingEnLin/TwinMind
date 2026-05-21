from twin_mind.chunking.strategies import paragraph_chunks
from twin_mind.models.document import Document, Source


def test_paragraph_chunker_extracts_sections():
    text = "# Title\n\n## Section A\n\nfirst paragraph\nstill first.\n\nsecond paragraph.\n"
    doc = Document(id="x.md", source=Source(name="x.md"), text=text)
    chunks = list(paragraph_chunks(doc))
    assert len(chunks) == 2
    assert chunks[0].section == "Section A"
    assert "first paragraph" in chunks[0].text
    assert "second paragraph" in chunks[1].text
