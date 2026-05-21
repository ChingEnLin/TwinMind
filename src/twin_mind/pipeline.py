from collections.abc import Iterable

from twin_mind.chunking.strategies import chunk_documents
from twin_mind.embeddings.base import Embedder
from twin_mind.models.document import Document
from twin_mind.vectorstore.base import VectorStore


def index_documents(docs: Iterable[Document], embedder: Embedder, store: VectorStore) -> int:
    chunks = chunk_documents(docs)
    if not chunks:
        return 0
    vectors = embedder.embed([c.text for c in chunks])
    for c, v in zip(chunks, vectors, strict=True):
        c.embedding = v
    store.add(chunks)
    return len(chunks)
