import typer

from twin_mind.api.state import state
from twin_mind.config import settings
from twin_mind.embeddings.factory import make_embedder
from twin_mind.ingestion.factory import make_loaders_for
from twin_mind.pipeline import index_documents
from twin_mind.vectorstore.factory import make_vectorstore


def ingest(
    source: str = typer.Option("local", help="loader: local | github | all"),
    rebuild: bool = typer.Option(
        False, "--rebuild", help="Drop and rebuild the index from scratch"
    ),
) -> None:
    """Ingest documents into the configured vector store."""
    if source not in {"local", "github", "all"}:
        raise typer.BadParameter("source must be one of: local, github, all")

    embedder = make_embedder(settings.EMBEDDER)
    store = make_vectorstore(settings.VECTORSTORE)
    if rebuild and hasattr(store, "reset"):
        store.reset()
        typer.echo("index reset")

    loader = make_loaders_for(source)
    n = index_documents(loader.load(), embedder, store)
    typer.echo(f"indexed {n} new chunks from --source {source} (store now has {len(store)})")

    # Drop any cached retriever so the next request sees the fresh index.
    state.retriever = None
