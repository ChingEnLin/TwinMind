import asyncio
from collections import defaultdict
from pathlib import Path

import typer

from twin_mind.api.state import state
from twin_mind.eval.metrics import citation_precision, refusal_correct, retrieval_recall
from twin_mind.eval.metrics.groundedness import groundedness_score
from twin_mind.eval.runner import EvalResult, load_cases, run_case


def eval_cmd(
    suite: str = typer.Option("smoke", help="suite name (smoke|full)"),
    path: str | None = typer.Option(None, help="explicit path to a YAML suite"),
    judge: bool = typer.Option(
        False, "--judge", help="run Claude-as-judge groundedness scoring (costs $)"
    ),
    report: str | None = typer.Option(
        None, "--report", help="write a markdown report to this path"
    ),
) -> None:
    """Run an eval suite and report per-metric scores."""
    suite_path = Path(path) if path else Path("eval/golden") / f"{suite}.yaml"
    if not suite_path.exists():
        typer.echo(f"suite not found: {suite_path}")
        raise typer.Exit(code=2)

    cases = load_cases(suite_path)

    async def run_all() -> int:
        results: list[EvalResult] = []
        for i, case in enumerate(cases, 1):
            res = await run_case(state, case)
            if judge and not res.skipped and not res.refused:
                verdict = await groundedness_score(res)
                res.judge_verdict = verdict  # type: ignore[attr-defined]
            results.append(res)
            _print_case_line(i, res)

        _print_summary(results, with_judge=judge)
        if report:
            Path(report).write_text(_render_markdown(results, suite, with_judge=judge))
            typer.echo(f"\nwrote report: {report}")
        return 0 if _suite_passed(results) else 1

    code = asyncio.run(run_all())
    raise typer.Exit(code=code)


def _print_case_line(i: int, res: EvalResult) -> None:
    if res.skipped:
        typer.echo(f"[SKIP] {i:>2}. {res.case.id}: {res.case.question}")
        return
    mark = "PASS" if res.passed else "FAIL"
    typer.echo(f"[{mark}] {i:>2}. {res.case.id}: {res.case.question}")
    if not res.passed:
        typer.echo(f"        reason: {res.reason}")
        typer.echo(f"        answer: {res.answer[:200]}")


def _print_summary(results: list[EvalResult], with_judge: bool) -> None:
    typer.echo("\n" + "=" * 60)
    typer.echo("PER-METRIC SUMMARY")
    typer.echo("=" * 60)

    scored: list[EvalResult] = [r for r in results if not r.skipped]

    recall_scores = [v for r in scored if (v := retrieval_recall(r)) is not None]
    citation_scores = [v for r in scored if (v := citation_precision(r)) is not None]
    refusal_scores = [v for r in scored if (v := refusal_correct(r)) is not None]

    typer.echo(f"retrieval_recall@K   : {_mean(recall_scores):.3f}  (n={len(recall_scores)})")
    typer.echo(f"citation_precision   : {_mean(citation_scores):.3f}  (n={len(citation_scores)})")
    typer.echo(
        f"refusal_correctness  : {_mean([1.0 if x else 0.0 for x in refusal_scores]):.3f}"
        f"  (n={len(refusal_scores)})"
    )
    if with_judge:
        judge_scores = [
            v.score for r in scored if (v := getattr(r, "judge_verdict", None)) is not None
        ]
        typer.echo(
            f"answer_faithfulness  : {_mean(judge_scores):.3f}"
            f"  (n={len(judge_scores)}, judge=Haiku)"
        )

    typer.echo("\nBY CATEGORY")
    by_cat: dict[str, list[EvalResult]] = defaultdict(list)
    for r in scored:
        by_cat[r.case.category].append(r)
    for cat in sorted(by_cat):
        rs = by_cat[cat]
        passes = sum(1 for r in rs if r.passed)
        typer.echo(f"  {cat:<28} {passes}/{len(rs)}")

    skipped = sum(1 for r in results if r.skipped)
    passed = sum(1 for r in scored if r.passed)
    typer.echo(f"\nTOTAL: {passed}/{len(scored)} passed ({skipped} skipped)")


def _suite_passed(results: list[EvalResult]) -> bool:
    return all(r.passed for r in results if not r.skipped)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _render_markdown(results: list[EvalResult], suite: str, with_judge: bool) -> str:
    scored = [r for r in results if not r.skipped]
    recall = [v for r in scored if (v := retrieval_recall(r)) is not None]
    cit = [v for r in scored if (v := citation_precision(r)) is not None]
    ref = [v for r in scored if (v := refusal_correct(r)) is not None]

    lines = [
        f"# Eval report — `{suite}`",
        "",
        f"**{sum(1 for r in scored if r.passed)}/{len(scored)} cases passed**"
        f" ({sum(1 for r in results if r.skipped)} skipped)",
        "",
        "| Metric | Score | N |",
        "| --- | --- | --- |",
        f"| retrieval_recall@K | {_mean(recall):.3f} | {len(recall)} |",
        f"| citation_precision | {_mean(cit):.3f} | {len(cit)} |",
        f"| refusal_correctness | {_mean([1.0 if x else 0.0 for x in ref]):.3f} | {len(ref)} |",
    ]
    if with_judge:
        judge = [v.score for r in scored if (v := getattr(r, "judge_verdict", None)) is not None]
        lines.append(f"| answer_faithfulness (Haiku) | {_mean(judge):.3f} | {len(judge)} |")

    failures = [r for r in scored if not r.passed]
    if failures:
        lines.extend(["", "## Failures", ""])
        for r in failures:
            lines.append(f"- **{r.case.id}** ({r.case.category}): {r.case.question}")
            lines.append(f"  - {r.reason}")
    return "\n".join(lines) + "\n"
