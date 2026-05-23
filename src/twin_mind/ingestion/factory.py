from collections.abc import Iterable

from twin_mind.config import settings
from twin_mind.ingestion.base import SourceLoader
from twin_mind.ingestion.github_repos import GitHubRepoLoader
from twin_mind.ingestion.local_docs import LocalDocsLoader
from twin_mind.models.document import Document


def make_loader(name: str) -> SourceLoader:
    if name == "local":
        return LocalDocsLoader(settings.samples_path)
    if name == "github":
        return GitHubRepoLoader()
    raise ValueError(f"unknown loader: {name}")


class _MultiLoader:
    """Chain multiple loaders into one ``load()`` stream."""

    name = "multi"

    def __init__(self, loaders: list[SourceLoader]) -> None:
        self._loaders = loaders

    def load(self) -> Iterable[Document]:
        for loader in self._loaders:
            yield from loader.load()


def make_loaders_for(source: str) -> SourceLoader:
    """``source`` is "local", "github", or "all"."""
    if source == "all":
        return _MultiLoader([make_loader("local"), make_loader("github")])
    return make_loader(source)
