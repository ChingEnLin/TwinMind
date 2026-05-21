import typer

from twin_mind.cli import eval_cmd, ingest, query

app = typer.Typer(help="TwinMind CLI", no_args_is_help=True)
app.command("ingest")(ingest.ingest)
app.command("query")(query.query)
app.command("eval")(eval_cmd.eval_cmd)


if __name__ == "__main__":
    app()
