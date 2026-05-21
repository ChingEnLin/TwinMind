from collections.abc import Iterable
from typing import Protocol

from twin_mind.models.document import Document


class SourceLoader(Protocol):
    name: str

    def load(self) -> Iterable[Document]: ...
