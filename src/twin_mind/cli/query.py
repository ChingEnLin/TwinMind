import asyncio

import typer

from twin_mind.api.state import state
from twin_mind.config import settings
from twin_mind.generation.citations import build_citations
from twin_mind.generation.grounding import enforce_grounding


def query(question: str = typer.Argument(...)) -> None:
    """Run a single grounded query and print the answer + citations."""

    async def run() -> None:
        retriever = state.ensure_index()
        retrieved = retriever.retrieve(question)
        if not retrieved:
            typer.echo("No documents indexed.")
            raise typer.Exit(code=1)

        llm = state.llm()
        full = ""
        async for ev in llm.stream_answer(
            question, retrieved, max_tokens=settings.LLM_MAX_OUTPUT_TOKENS
        ):
            if ev.kind == "token" and ev.text:
                typer.echo(ev.text, nl=False)
                full += ev.text
        typer.echo("")

        final, refused, reason = enforce_grounding(full)
        if refused and final != full:
            typer.echo(f"\n[GROUNDING] forced refusal: {final}")
        typer.echo("\n--- citations ---")
        for c in build_citations(final, retrieved):
            typer.echo(f"  [{c.id}] {c.source}" + (f" — {c.section}" if c.section else ""))
        if refused:
            typer.echo(f"refused: {reason}")

    asyncio.run(run())
