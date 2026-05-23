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

    def ensure_index(self, rebuild: bool = False) -> Retriever:
        """Build (or reuse) the retriever.

        If the configured vector store already has data and `rebuild` is False,
        we skip re-ingestion — this is the persistence win in Phase 2.
        """
        with self._lock:
            if self.retriever is not None and not rebuild:
                return self.retriever
            embedder = make_embedder(settings.EMBEDDER)
            store = make_vectorstore(settings.VECTORSTORE)
            if rebuild and hasattr(store, "reset"):
                store.reset()
            if len(store) == 0:
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
