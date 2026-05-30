"""Render a QualityReport to a terminal or JSON.

Kept separate from the Typer commands so tests can import the renderer
without standing up a Typer app.
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from legal_quality_gate import QualityReport, Severity

_SEVERITY_STYLE = {
    Severity.ERROR: "bold red",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
}


def print_text_report(report: QualityReport, *, source: Path, console: Console) -> None:
    """Pretty-print a report. Errors are red, warnings yellow."""
    counts = _counts(report)
    summary = (
        f"[bold]{source.name}[/]\n"
        f"Score: [bold]{report.score:.0f}[/]/100\n"
        f"Findings: {counts[Severity.ERROR]} errors, "
        f"{counts[Severity.WARNING]} warnings, {counts[Severity.INFO]} info"
    )
    console.print(Panel(summary, title="Anchor Quality Gate", expand=False))

    if not report.findings:
        console.print("[green]No findings.[/]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Severity", width=8)
    table.add_column("Rule", width=24)
    table.add_column("Segment", width=12)
    table.add_column("Message")

    # Errors first, then warnings, then info.
    severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    for finding in sorted(report.findings, key=lambda f: (severity_order[f.severity], f.segment_id)):
        style = _SEVERITY_STYLE[finding.severity]
        table.add_row(
            f"[{style}]{finding.severity.value.upper()}[/]",
            finding.rule_id,
            finding.segment_id,
            finding.message,
        )

    console.print(table)


def report_as_json(report: QualityReport) -> str:
    """Serialize the report as JSON via Pydantic, prettified."""
    return json.dumps(report.model_dump(mode="json"), indent=2, default=str)


def _counts(report: QualityReport) -> dict[Severity, int]:
    out = {Severity.ERROR: 0, Severity.WARNING: 0, Severity.INFO: 0}
    for f in report.findings:
        out[f.severity] += 1
    return out


def has_errors(report: QualityReport) -> bool:
    return any(f.severity is Severity.ERROR for f in report.findings)
