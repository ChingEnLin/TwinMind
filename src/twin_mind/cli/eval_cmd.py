import asyncio
from pathlib import Path

import typer

from twin_mind.api.state import state
from twin_mind.eval.runner import load_cases, run_case


def eval_cmd(
    suite: str = typer.Option("smoke", help="suite name (smoke|full)"),
    path: str | None = typer.Option(None, help="explicit path to a YAML suite"),
) -> None:
    """Run an eval suite and report pass/fail per case."""
    suite_path = Path(path) if path else Path("eval/golden") / f"{suite}.yaml"
    if not suite_path.exists():
        typer.echo(f"suite not found: {suite_path}")
        raise typer.Exit(code=2)

    cases = load_cases(suite_path)

    async def run_all() -> int:
        passes = 0
        skipped = 0
        for i, case in enumerate(cases, 1):
            res = await run_case(state, case)
            if res.skipped:
                typer.echo(f"[SKIP] {i}. {case.question}")
                typer.echo(f"        reason: {res.reason}")
                skipped += 1
                continue
            mark = "PASS" if res.passed else "FAIL"
            typer.echo(f"[{mark}] {i}. {case.question}")
            typer.echo(f"        refused={res.refused} citations={res.citations}")
            if not res.passed:
                typer.echo(f"        reason: {res.reason}")
                typer.echo(f"        answer: {res.answer[:240]}")
            else:
                passes += 1
        ran = len(cases) - skipped
        typer.echo(f"\n{passes}/{ran} passed ({skipped} skipped)")
        return 0 if passes == ran else 1

    code = asyncio.run(run_all())
    raise typer.Exit(code=code)
