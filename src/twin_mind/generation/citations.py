import re

from twin_mind.models.document import Citation
from twin_mind.vectorstore.base import ScoredChunk

_CITE_RE = re.compile(r"\[([^\[\]\s][^\[\]]*?)\]")


def extract_cited_ids(answer: str) -> list[str]:
    seen: list[str] = []
    for m in _CITE_RE.finditer(answer):
        cid = m.group(1).strip()
        if cid and cid not in seen:
            seen.append(cid)
    return seen


def build_citations(answer: str, retrieved: list[ScoredChunk]) -> list[Citation]:
    by_id = {s.chunk.id: s.chunk for s in retrieved}
    out: list[Citation] = []
    for cid in extract_cited_ids(answer):
        ch = by_id.get(cid)
        if ch is None:
            continue
        out.append(
            Citation(
                id=ch.id,
                source=ch.source.name,
                section=ch.section,
                url=ch.source.url,
            )
        )
    return out
