"""`python -m tools.eval.cli ...` command-line surface."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from legal_citations import NormalizeCaseOutput
from legal_llm_gateway import FakeLLMClient
from tools.eval.adversarial import generate_adversarial
from tools.eval.calibration import compute_calibration
from tools.eval.cache import NullCache, ResponseCache
from tools.eval.dataset import iter_dataset, load_dataset, write_dataset
from tools.eval.reporter import (
    print_calibration,
    print_report,
    print_threshold_violations,
)
from tools.eval.runner import RunConfig, run_eval
from tools.eval.scorers import (
    BluebookFuzzy,
    ExactMatch,
    FieldMatch,
    SchemaValid,
)
from tools.eval.store import open_store, write_report
from tools.eval.thresholds import check_absolute, check_regression, load_thresholds

app = typer.Typer(
    name="lqg-eval",
    help="Anchor Quality Gate LLM eval harness",
    no_args_is_help=True,
    add_completion=False,
)


_DEFAULT_RESULTS_DB = Path("tools/eval/results.duckdb")


def _make_scorers() -> list:
    return [
        SchemaValid(),
        ExactMatch(field="canonical"),
        BluebookFuzzy(field="canonical"),
        FieldMatch(
            fields=("case_name", "year", "pinpoint", "court"),
            name="field_match",
        ),
    ]


@app.command()
def run(
    dataset: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    prompt_id: str = typer.Option(
        "bluebook.normalize_case@v1", "--prompt-id"
    ),
    model: list[str] = typer.Option(
        ["fake/canned"], "--model", "-m",
        help="Model identifier(s) to evaluate; repeat for multiple.",
    ),
    cache_dir: Optional[Path] = typer.Option(
        Path("tools/eval/.cache"), "--cache-dir",
        help="Response cache directory; use --no-cache to disable.",
    ),
    no_cache: bool = typer.Option(False, "--no-cache"),
    db_path: Path = typer.Option(_DEFAULT_RESULTS_DB, "--db"),
    fake: bool = typer.Option(
        True, "--fake/--real",
        help="Use FakeLLMClient (default; for offline runs) vs LiteLLMClient.",
    ),
) -> None:
    """Run an eval and persist the report."""
    console = Console()
    cases = load_dataset(dataset)
    cache = ResponseCache(cache_dir) if not no_cache and cache_dir else NullCache()

    if fake:
        # Smoke runs ship pre-baked canned answers so tests/dev loops
        # don't need API keys; use a real client by passing --real
        # with provider env vars configured.
        responses = {}
        client = FakeLLMClient(
            responses=responses,
            default_output=NormalizeCaseOutput(canonical="(fake)", confidence=0.9),
        )
    else:
        from legal_llm_gateway import LiteLLMClient
        client = LiteLLMClient()

    config = RunConfig(
        prompt_id=prompt_id,
        output_schema=NormalizeCaseOutput,
        models=list(model),
        scorers=_make_scorers(),
        cache=cache,
    )

    report = asyncio.run(run_eval(cases, client=client, config=config))
    report.dataset_path = str(dataset)

    expected_by_case = {c.id: c.expected for c in cases}
    with open_store(db_path) as con:
        write_report(con, report, expected_by_case=expected_by_case)

    print_report(report, console=console)


@app.command("calibration")
def calibration(
    dataset: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    prompt_id: str = typer.Option("bluebook.normalize_case@v1", "--prompt-id"),
    model: list[str] = typer.Option(["fake/canned"], "--model", "-m"),
    fake: bool = typer.Option(True, "--fake/--real"),
) -> None:
    """Run an eval and print calibration diagrams per model."""
    console = Console()
    cases = load_dataset(dataset)
    if fake:
        client = FakeLLMClient(
            default_output=NormalizeCaseOutput(canonical="(fake)", confidence=0.9),
        )
    else:
        from legal_llm_gateway import LiteLLMClient
        client = LiteLLMClient()
    config = RunConfig(
        prompt_id=prompt_id,
        output_schema=NormalizeCaseOutput,
        models=list(model),
        scorers=_make_scorers(),
    )
    report = asyncio.run(run_eval(cases, client=client, config=config))
    for m in report.models:
        cr = [r for r in report.case_results if r.model == m]
        calib = compute_calibration(cr)
        print_calibration(calib, model=m, console=console)


@app.command("thresholds-check")
def thresholds_check(
    thresholds_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    run_id: Optional[str] = typer.Option(None, "--run-id"),
    prompt_id: str = typer.Option("bluebook.normalize_case@v1", "--prompt-id"),
    db_path: Path = typer.Option(_DEFAULT_RESULTS_DB, "--db"),
    regression: bool = typer.Option(
        True, "--regression/--no-regression",
        help="Also compare current vs previous run for regression.",
    ),
) -> None:
    """Check absolute + optional regression thresholds against the latest run."""
    console = Console()
    thresholds = load_thresholds(thresholds_path)
    if prompt_id not in thresholds:
        console.print(f"[yellow]No thresholds configured for {prompt_id}.[/]")
        raise typer.Exit(code=0)
    pt = thresholds[prompt_id]

    with open_store(db_path) as con:
        from tools.eval.store import latest_run_ids, mean_score_for_run

        if run_id is None:
            ids = latest_run_ids(con, prompt_id, limit=2)
            if not ids:
                console.print("[red]no runs stored yet.[/]")
                raise typer.Exit(code=1)
            run_id, prev_run_id = ids[0], ids[1] if len(ids) > 1 else None
        else:
            prev_run_id = None
            if regression:
                ids = latest_run_ids(con, prompt_id, limit=10)
                prev_run_id = next((r for r in ids if r != run_id), None)

        violations: list = []
        for model, mt in pt.models.items():
            acc = mean_score_for_run(
                con, run_id, model=model, scorer=mt.accuracy_scorer
            )
            cost_row = con.execute(
                """
                SELECT AVG(cost_cents), QUANTILE_CONT(latency_ms, 0.95)
                FROM case_results WHERE run_id = ? AND model = ?
                """,
                (run_id, model),
            ).fetchone()
            cost = float(cost_row[0] or 0)
            p95 = int(cost_row[1] or 0)
            violations.extend(
                check_absolute(
                    pt, model=model,
                    accuracy=acc, mean_cost_cents=cost, p95_latency_ms=p95,
                )
            )
            if regression and prev_run_id is not None:
                prev_acc = mean_score_for_run(
                    con, prev_run_id, model=model, scorer=mt.accuracy_scorer
                )
                prev_cost_row = con.execute(
                    """
                    SELECT AVG(cost_cents), QUANTILE_CONT(latency_ms, 0.95)
                    FROM case_results WHERE run_id = ? AND model = ?
                    """,
                    (prev_run_id, model),
                ).fetchone()
                prev_cost = float(prev_cost_row[0] or 0)
                prev_p95 = int(prev_cost_row[1] or 0)
                violations.extend(
                    check_regression(
                        pt, model=model,
                        current_accuracy=acc, baseline_accuracy=prev_acc,
                        current_mean_cost_cents=cost,
                        baseline_mean_cost_cents=prev_cost,
                        current_p95_ms=p95,
                        baseline_p95_ms=prev_p95,
                    )
                )

    print_threshold_violations(violations, console=console)
    if violations:
        raise typer.Exit(code=1)


@app.command("generate-adversarial")
def generate_adversarial_cmd(
    seed_dataset: Path = typer.Argument(..., exists=True, dir_okay=False),
    out: Path = typer.Option(..., "--out", help="Output JSONL path."),
    per_case: int = typer.Option(3, "--per-case"),
    seed: int = typer.Option(1729, "--seed"),
) -> None:
    """Generate adversarial mutants from a hand-labeled seed dataset."""
    console = Console()
    cases = load_dataset(seed_dataset)
    mutants = generate_adversarial(cases, per_case=per_case, seed=seed)
    write_dataset(out, mutants)
    console.print(
        f"[green]Wrote {len(mutants)} mutants from {len(cases)} seeds[/] → {out}"
    )


if __name__ == "__main__":
    app()
