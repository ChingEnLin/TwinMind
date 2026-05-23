"""Chroma vector store adapter (embedded persistent client).

Stores chunks in a local SQLite-backed Chroma DB. We bring our own embeddings
in (Chroma is told `embedding_function=None`) so the Embedder Protocol stays
the single source of truth.

Distance → similarity: Chroma returns cosine *distance* (0 = identical,
2 = opposite). We convert to similarity = 1 - distance for parity with
the in-memory store's cosine score.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from twin_mind.config import settings
from twin_mind.models.document import Chunk, Source
from twin_mind.vectorstore.base import ScoredChunk


class ChromaVectorStore:
    name = "chroma"

    def __init__(
        self,
        path: str | None = None,
        collection: str | None = None,
        in_memory: bool = False,
    ) -> None:
        import chromadb

        self.collection_name = collection or settings.CHROMA_COLLECTION

        if in_memory:
            self._client = chromadb.EphemeralClient()
        else:
            self.path = Path(path or settings.CHROMA_PATH)
            self.path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.path))

        # cosine space; we supply embeddings explicitly so no embedding_function.
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for c in chunks:
            if c.embedding is None:
                raise ValueError(f"chunk {c.id} missing embedding")
            ids.append(c.id)
            embeddings.append(c.embedding)
            documents.append(c.text)
            metadatas.append(
                {
                    "doc_id": c.doc_id,
                    "source_name": c.source.name,
                    "source_url": c.source.url or "",
                    "section": c.section or "",
                    "metadata_json": json.dumps(c.metadata or {}),
                }
            )
        # upsert so re-ingesting is idempotent.
        self._collection.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    def search(self, query_embedding: list[float], k: int) -> list[ScoredChunk]:
        if self._collection.count() == 0:
            return []
        res = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]

        out: list[ScoredChunk] = []
        for cid, text, meta, dist in zip(ids, docs, metas, dists, strict=True):
            meta = meta or {}
            try:
                extra = json.loads(meta.get("metadata_json") or "{}")
            except json.JSONDecodeError:
                extra = {}
            chunk = Chunk(
                id=cid,
                doc_id=meta.get("doc_id") or "",
                source=Source(
                    name=meta.get("source_name") or "",
                    url=meta.get("source_url") or None,
                ),
                text=text or "",
                section=meta.get("section") or None,
                metadata=extra,
            )
            # cosine distance → similarity
            similarity = 1.0 - float(dist)
            out.append(ScoredChunk(chunk, similarity))
        return out

    def reset(self) -> None:
        """Drop and recreate the collection. Used by ``tm ingest --rebuild``."""
        try:
            self._client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def all_chunks(self) -> Iterable[Chunk]:
        if self._collection.count() == 0:
            return
        # Paginate to avoid loading a huge collection into memory at once.
        page_size = 500
        offset = 0
        while True:
            res = self._collection.get(
                limit=page_size,
                offset=offset,
                include=["documents", "metadatas"],
            )
            ids = res.get("ids") or []
            if not ids:
                return
            docs = res.get("documents") or [""] * len(ids)
            metas = res.get("metadatas") or [{}] * len(ids)
            for cid, text, meta in zip(ids, docs, metas, strict=True):
                meta = meta or {}
                try:
                    extra = json.loads(meta.get("metadata_json") or "{}")
                except json.JSONDecodeError:
                    extra = {}
                yield Chunk(
                    id=cid,
                    doc_id=meta.get("doc_id") or "",
                    source=Source(
                        name=meta.get("source_name") or "",
                        url=meta.get("source_url") or None,
                    ),
                    text=text or "",
                    section=meta.get("section") or None,
                    metadata=extra,
                )
            if len(ids) < page_size:
                return
            offset += page_size

    def __len__(self) -> int:
        return int(self._collection.count())
