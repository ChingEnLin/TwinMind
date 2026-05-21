from threading import Lock

from twin_mind.config import settings
from twin_mind.embeddings.factory import make_embedder
from twin_mind.generation.base import LLMClient
from twin_mind.generation.factory import make_llm
from twin_mind.ingestion.local_docs import LocalDocsLoader
from twin_mind.pipeline import index_documents
from twin_mind.retrieval.retriever import Retriever
from twin_mind.vectorstore.factory import make_vectorstore


class AppState:
    def __init__(self) -> None:
        self.retriever: Retriever | None = None
        self._llm: LLMClient | None = None
        self._lock = Lock()

    def ensure_index(self) -> Retriever:
        with self._lock:
            if self.retriever is not None:
                return self.retriever
            embedder = make_embedder("stub")
            store = make_vectorstore("in_memory")
            loader = LocalDocsLoader(settings.samples_path)
            index_documents(loader.load(), embedder, store)
            self.retriever = Retriever(embedder, store, top_k=settings.TOP_K)
            return self.retriever

    def llm(self) -> LLMClient:
        with self._lock:
            if self._llm is None:
                self._llm = make_llm("anthropic")
            return self._llm


state = AppState()
