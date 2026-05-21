from pathlib import Path

import pytest

from twin_mind.embeddings.factory import make_embedder
from twin_mind.generation.citations import build_citations
from twin_mind.generation.grounding import enforce_grounding
from twin_mind.ingestion.local_docs import LocalDocsLoader
from twin_mind.pipeline import index_documents
from twin_mind.retrieval.retriever import Retriever
from twin_mind.vectorstore.factory import make_vectorstore


@pytest.mark.asyncio
async def test_full_happy_path_with_mocked_llm(tmp_path: Path, fake_llm):
    (tmp_path / "experience").mkdir()
    (tmp_path / "experience" / "virtonomy.md").write_text(
        "# Virtonomy\n\n## Role\n\nChing-En built a Python ingestion pipeline for medical CAD files.\n"
    )

    embedder = make_embedder("stub")
    store = make_vectorstore("in_memory")
    loader = LocalDocsLoader(tmp_path)
    n = index_documents(loader.load(), embedder, store)
    assert n >= 1

    retriever = Retriever(embedder, store, top_k=4)
    retrieved = retriever.retrieve("What did Ching-En do at Virtonomy?")
    assert retrieved, "expected at least one retrieved chunk"

    full = ""
    async for ev in fake_llm.stream_answer("q", retrieved, max_tokens=400):
        if ev.kind == "token":
            full += ev.text

    final, refused, _ = enforce_grounding(full)
    assert refused is False, f"unexpected refusal: {final}"
    cites = build_citations(final, retrieved)
    assert cites, f"no citations parsed from: {final}"
    assert cites[0].source.endswith("virtonomy.md")
