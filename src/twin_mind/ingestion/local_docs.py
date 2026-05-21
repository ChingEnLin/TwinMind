from collections.abc import Iterable
from pathlib import Path

from twin_mind.models.document import Document, Source


class LocalDocsLoader:
    name = "local"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def load(self) -> Iterable[Document]:
        if not self.root.exists():
            return
        for path in sorted(self.root.rglob("*.md")):
            rel = path.relative_to(self.root).as_posix()
            text = path.read_text(encoding="utf-8")
            yield Document(
                id=rel,
                source=Source(name=rel, url=None),
                text=text,
                metadata={"path": str(path)},
            )
