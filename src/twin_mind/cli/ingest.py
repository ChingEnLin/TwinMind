import typer

from twin_mind.api.state import state


def ingest(
    source: str = typer.Option("local", help="loader name"),
    rebuild: bool = typer.Option(
        False, "--rebuild", help="Drop and rebuild the index from scratch"
    ),
) -> None:
    """Ingest documents into the configured vector store."""
    if source != "local":
        raise typer.BadParameter("Phase 2 only supports --source local")
    retriever = state.ensure_index(rebuild=rebuild)
    typer.echo(f"indexed {len(retriever.store)} chunks from local samples")
