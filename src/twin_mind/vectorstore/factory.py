from twin_mind.vectorstore.adapters.in_memory import InMemoryVectorStore
from twin_mind.vectorstore.base import VectorStore


def make_vectorstore(name: str = "in_memory") -> VectorStore:
    if name == "in_memory":
        return InMemoryVectorStore()
    raise ValueError(f"unknown vectorstore: {name}")
