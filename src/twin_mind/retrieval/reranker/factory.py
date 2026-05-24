from twin_mind.retrieval.reranker.base import Reranker


def make_reranker(name: str = "identity") -> Reranker:
    if name in ("identity", "none"):
        from twin_mind.retrieval.reranker.adapters.identity import IdentityReranker

        return IdentityReranker()
    if name == "cross_encoder":
        from twin_mind.retrieval.reranker.adapters.cross_encoder import CrossEncoderReranker

        return CrossEncoderReranker()
    if name == "claude":
        from twin_mind.retrieval.reranker.adapters.claude import ClaudeReranker

        return ClaudeReranker()
    raise ValueError(f"unknown reranker: {name}")
