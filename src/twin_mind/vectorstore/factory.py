from twin_mind.vectorstore.base import VectorStore


def make_vectorstore(name: str = "in_memory") -> VectorStore:
    if name == "in_memory":
        from twin_mind.vectorstore.adapters.in_memory import InMemoryVectorStore

        return InMemoryVectorStore()
    if name == "chroma":
        from twin_mind.vectorstore.adapters.chroma import ChromaVectorStore

        return ChromaVectorStore()
    raise ValueError(f"unknown vectorstore: {name}")
