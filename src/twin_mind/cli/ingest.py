import typer

from twin_mind.api.state import state


def ingest(source: str = typer.Option("local", help="loader name")) -> None:
    """Ingest documents into the in-memory index. Phase 1 only supports 'local'."""
    if source != "local":
        raise typer.BadParameter("Phase 1 only supports --source local")
    retriever = state.ensure_index()
    typer.echo(f"indexed {len(retriever.store)} chunks from local samples")
