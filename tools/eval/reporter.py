"""Rich-formatted report rendering."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tools.eval.calibration import CalibrationReport
from tools.eval.thresholds import ThresholdViolation
from tools.eval.types import RunReport


def print_report(report: RunReport, *, console: Console | None = None) -> None:
    console = console or Console()
    duration = (report.finished_at - report.started_at).total_seconds()
    summary = (
        f"[bold]prompt[/]: {report.prompt_id}\n"
        f"[bold]cases[/]: {len(report.case_results) // max(1, len(report.models))} "
        f"per model × {len(report.models)} model(s)\n"
        f"[bold]duration[/]: {duration:.1f}s"
    )
    console.print(Panel(summary, title="LLM eval run", expand=False))

    scorer_names = sorted({s for cr in report.case_results for s in cr.scores})
    table = Table(show_header=True, header_style="bold")
    table.add_column("Model")
    table.add_column("schema_valid", justify="right")
    for sc in scorer_names:
        table.add_column(sc, justify="right")
    table.add_column("$/call", justify="right")
    table.add_column("p95 ms", justify="right")

    for model in report.models:
        row = [model, f"{report.schema_valid_rate(model) * 100:.1f}%"]
        for sc in scorer_names:
            row.append(f"{report.mean_score(model, sc) * 100:.1f}%")
        row.append(f"{report.mean_cost_cents(model) / 100:.4f}")
        row.append(str(report.p95_latency_ms(model)))
        table.add_row(*row)
    console.print(table)


def print_calibration(
    calib: CalibrationReport,
    *,
    model: str,
    console: Console | None = None,
) -> None:
    console = console or Console()
    well = "[green]well-calibrated[/]" if calib.well_calibrated() else "[red]drift[/]"
    console.print(
        Panel(
            f"[bold]{model}[/] · ECE = {calib.ece:.3f} · {well} "
            f"· n = {calib.n_scored}",
            expand=False,
        )
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Bucket")
    table.add_column("Count", justify="right")
    table.add_column("Mean conf.", justify="right")
    table.add_column("Accuracy", justify="right")
    table.add_column("Δ", justify="right")
    for b in calib.buckets:
        if b.count == 0:
            continue
        delta = b.accuracy - b.mean_confidence
        delta_style = (
            "green" if abs(delta) < 0.05 else "yellow" if abs(delta) < 0.10 else "red"
        )
        table.add_row(
            f"{b.lo:.1f}-{b.hi:.1f}",
            str(b.count),
            f"{b.mean_confidence:.2f}",
            f"{b.accuracy:.2f}",
            f"[{delta_style}]{delta:+.2f}[/]",
        )
    console.print(table)


def print_threshold_violations(
    violations: list[ThresholdViolation],
    *,
    console: Console | None = None,
) -> None:
    console = console or Console()
    if not violations:
        console.print("[green]All thresholds satisfied.[/]")
        return
    table = Table(show_header=True, header_style="bold red")
    table.add_column("Prompt")
    table.add_column("Model")
    table.add_column("Kind")
    table.add_column("Observed")
    table.add_column("Threshold")
    table.add_column("Detail")
    for v in violations:
        table.add_row(
            v.prompt_id, v.model, v.kind,
            f"{v.observed:.3f}", f"{v.threshold:.3f}", v.detail,
        )
    console.print(table)
