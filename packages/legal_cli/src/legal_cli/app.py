"""The `lqg` Typer app.

Two commands ship in v0:

- `lqg check <path>` — parse a .docx, run the quality-gate pipeline,
  print a report. Exit code 1 if any error-severity findings are
  produced; 0 otherwise.
- `lqg cites <path>` — parse a .docx, extract every citation, print
  them in a table.

Future v0/v1 additions: `lqg fix` (uses the annotated_writer that lands
next), `lqg skill build` (in legal_skill_kit).
"""

from __future__ import annotations

import asyncio
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from legal_citations import extract_citations_in_text
from legal_docx import parse_docx
from legal_quality_gate import CheckContext, Pipeline, Policy, load_policy

from legal_cli._registry import build_default_registry, load_rules
from legal_cli._report import has_errors, print_text_report, report_as_json

app = typer.Typer(
    name="lqg",
    help="Anchor Quality Gate CLI",
    no_args_is_help=True,
    add_completion=False,
)


class OutputFormat(str, Enum):
    TEXT = "text"
    JSON = "json"


@app.command()
def check(
    path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    policy: Optional[Path] = typer.Option(
        None, "--policy", "-p", exists=True, dir_okay=False, readable=True,
        help="Policy YAML controlling enabled checkers, severity overrides, auto-fix globs.",
    ),
    rules: Optional[Path] = typer.Option(
        None, "--rules", "-r", exists=True, dir_okay=False, readable=True,
        help="Court-rules YAML consumed by the formatting checker.",
    ),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output", "-o"),
) -> None:
    """Run the quality gate against a .docx and print findings."""
    console = Console()

    result = parse_docx(path)
    policy_obj = load_policy(policy) if policy else Policy()
    registry = build_default_registry(rules=load_rules(rules))

    ctx = CheckContext(text_loader=result.text_loader)
    report = asyncio.run(
        Pipeline(registry, policy=policy_obj).run(result.document, ctx)
    )

    if output is OutputFormat.JSON:
        typer.echo(report_as_json(report))
    else:
        print_text_report(report, source=path, console=console)

    raise typer.Exit(code=1 if has_errors(report) else 0)


@app.command()
def cites(
    path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output", "-o"),
) -> None:
    """Extract every citation from a .docx and print them."""
    console = Console()
    result = parse_docx(path)

    rows: list[dict] = []
    for segment in result.document.segments:
        text = result.text_loader(segment)
        for extracted in extract_citations_in_text(text, segment_id=segment.id):
            rows.append(
                {
                    "segment_id": segment.id,
                    "type": extracted.eyecite_type,
                    "case_name": extracted.citation.parsed.case_name,
                    "raw_text": extracted.citation.raw_text,
                    "pinpoint": extracted.citation.parsed.pinpoint,
                    "signal": extracted.citation.parsed.signal,
                }
            )

    if output is OutputFormat.JSON:
        import json
        typer.echo(json.dumps(rows, indent=2))
        return

    if not rows:
        console.print("[yellow]No citations found.[/]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Segment", width=12)
    table.add_column("Type", width=18)
    table.add_column("Case")
    table.add_column("Cite")
    table.add_column("Pin")
    table.add_column("Signal")
    for row in rows:
        table.add_row(
            row["segment_id"],
            row["type"],
            row["case_name"] or "",
            row["raw_text"],
            row["pinpoint"] or "",
            row["signal"] or "",
        )
    console.print(table)
