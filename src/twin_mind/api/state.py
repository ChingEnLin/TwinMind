from threading import Lock

from twin_mind.config import settings
from twin_mind.embeddings.factory import make_embedder
from twin_mind.generation.base import LLMClient
from twin_mind.generation.factory import make_llm
from twin_mind.ingestion.factory import make_loaders_for
from twin_mind.pipeline import index_documents
from twin_mind.retrieval.bm25 import BM25Retriever
from twin_mind.retrieval.hybrid import HybridRetriever
from twin_mind.retrieval.reranked import RerankedRetriever
from twin_mind.retrieval.reranker.factory import make_reranker
from twin_mind.retrieval.retriever import Retriever
from twin_mind.vectorstore.factory import make_vectorstore


class AppState:
    def __init__(self) -> None:
        self.retriever: Retriever | HybridRetriever | RerankedRetriever | None = None
        self._llm: LLMClient | None = None
        self._lock = Lock()

    def ensure_index(
        self, rebuild: bool = False
    ) -> Retriever | HybridRetriever | RerankedRetriever:
        """Build (or reuse) the retriever.

        Behavior:
        - Reuse the cached retriever unless rebuild=True.
        - On rebuild, reset the store (if supported) before re-ingesting.
        - On empty store, ingest from ``settings.BOOTSTRAP_SOURCE`` (default
          "local" — server boot does NOT call GitHub unless explicitly set).
        - Wrap with HybridRetriever when ``settings.RETRIEVAL_MODE == "hybrid"``.
        """
        with self._lock:
            if self.retriever is not None and not rebuild:
                return self.retriever
            embedder = make_embedder(settings.EMBEDDER)
            store = make_vectorstore(settings.VECTORSTORE)
            if rebuild and hasattr(store, "reset"):
                store.reset()
            if len(store) == 0:
                loader = make_loaders_for(settings.BOOTSTRAP_SOURCE)
                index_documents(loader.load(), embedder, store)

            vector = Retriever(embedder, store, top_k=settings.TOP_K)

            mode = settings.RETRIEVAL_MODE
            if mode == "vector":
                base = vector
            elif mode == "bm25":
                base = _BM25OnlyRetriever(
                    BM25Retriever(store.all_chunks()), store, top_k=settings.TOP_K
                )
            else:  # "hybrid"
                bm25 = BM25Retriever(store.all_chunks())
                base = HybridRetriever(vector, bm25, top_k=settings.TOP_K)

            if settings.RERANKER != "none":
                self.retriever = RerankedRetriever(
                    base,
                    make_reranker(settings.RERANKER),
                    candidate_k=settings.RERANKER_CANDIDATE_K,
                    top_k=settings.TOP_K,
                )
            else:
                self.retriever = base
            return self.retriever

    def llm(self) -> LLMClient:
        with self._lock:
            if self._llm is None:
                self._llm = make_llm("anthropic")
            return self._llm


class _BM25OnlyRetriever:
    """Adapter that gives BM25 the same retrieve(query, k) shape as Retriever.

    Only used when RETRIEVAL_MODE=bm25 (for ablation/debugging). Production
    default is hybrid.
    """

    name = "bm25_only"

    def __init__(self, bm25: BM25Retriever, store, top_k: int) -> None:
        self._bm25 = bm25
        self.store = store
        self.top_k = top_k

    def retrieve(self, query: str, k: int | None = None):
        return self._bm25.retrieve(query, k or self.top_k)


state = AppState()
