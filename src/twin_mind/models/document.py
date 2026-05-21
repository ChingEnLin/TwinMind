from dataclasses import dataclass, field


@dataclass
class Source:
    name: str
    url: str | None = None


@dataclass
class Document:
    id: str
    source: Source
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    id: str
    doc_id: str
    source: Source
    text: str
    section: str | None = None
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Citation:
    id: str
    source: str
    section: str | None = None
    url: str | None = None
