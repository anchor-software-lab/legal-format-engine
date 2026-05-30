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

import os

from legal_citations import extract_citations_in_text
from legal_docx import parse_docx, write_annotated
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
    llm: bool = typer.Option(
        False, "--llm",
        help="Enable LLM-bound checkers (e.g. bluebook.case_form). "
             "Requires ANTHROPIC_API_KEY or OPENAI_API_KEY in env.",
    ),
) -> None:
    """Run the quality gate against a .docx and print findings."""
    console = Console()

    result = parse_docx(path)
    policy_obj = load_policy(policy) if policy else Policy()
    registry = build_default_registry(
        rules=load_rules(rules),
        llm_client=_build_llm_client() if llm else None,
    )

    ctx = CheckContext(text_loader=result.text_loader)
    report = asyncio.run(
        Pipeline(registry, policy=policy_obj).run(result.document, ctx)
    )

    if output is OutputFormat.JSON:
        typer.echo(report_as_json(report))
    else:
        print_text_report(report, source=path, console=console)

    raise typer.Exit(code=1 if has_errors(report) else 0)


def _build_llm_client():
    """Construct a LiteLLMClient. Imported lazily so the offline CLI
    path doesn't import litellm at all."""
    if not (
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OLLAMA_HOST")
    ):
        raise typer.BadParameter(
            "--llm requires ANTHROPIC_API_KEY, OPENAI_API_KEY, or "
            "OLLAMA_HOST in env. Skip --llm to run deterministic checkers only."
        )
    from legal_llm_gateway import LiteLLMClient  # lazy import — heavy

    return LiteLLMClient()


@app.command()
def fix(
    path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    policy: Optional[Path] = typer.Option(
        None, "--policy", "-p", exists=True, dir_okay=False, readable=True,
        help="Policy YAML; the auto_fix.allow globs are intersected with each finding's auto_apply_safe flag.",
    ),
    rules: Optional[Path] = typer.Option(
        None, "--rules", "-r", exists=True, dir_okay=False, readable=True,
    ),
    in_place: bool = typer.Option(
        False, "--in-place", help="Overwrite the original docx. Mutually exclusive with --out.",
    ),
    out: Optional[Path] = typer.Option(
        None, "--out", "-O", dir_okay=False, writable=True,
        help="Write the fixed docx to this path. Defaults to <original>.fixed.docx.",
    ),
) -> None:
    """Apply every auto-safe Suggestion to the docx and write a fixed copy."""
    console = Console()

    if in_place and out is not None:
        console.print("[red]--in-place and --out are mutually exclusive.[/]")
        raise typer.Exit(code=2)

    if in_place:
        target = path
    elif out is not None:
        target = out
    else:
        target = path.with_suffix(".fixed.docx")

    result = parse_docx(path)
    policy_obj = load_policy(policy) if policy else Policy()
    registry = build_default_registry(rules=load_rules(rules))

    ctx = CheckContext(text_loader=result.text_loader)
    report = asyncio.run(
        Pipeline(registry, policy=policy_obj).run(result.document, ctx)
    )

    safe_findings = [
        f for f in report.findings
        if f.suggestion is not None
        and f.suggestion.auto_apply_safe
        and (not policy_obj.auto_fix_allow or policy_obj.auto_fix_allowed(f.rule_id))
    ]
    safe_suggestions = [f.suggestion for f in safe_findings]

    if not safe_suggestions:
        console.print("[yellow]No auto-safe suggestions to apply.[/]")
        raise typer.Exit(code=0)

    write_annotated(
        original_path=path,
        suggestions=safe_suggestions,
        out_path=target,
        segment_ordinal_by_id=result.segment_ordinal_by_id,
    )

    rule_counts: dict[str, int] = {}
    for f in safe_findings:
        rule_counts[f.rule_id] = rule_counts.get(f.rule_id, 0) + 1
    summary = ", ".join(f"{count}×{rule}" for rule, count in sorted(rule_counts.items()))
    console.print(
        f"[green]Applied {len(safe_suggestions)} suggestion(s)[/] ({summary}) → {target}"
    )


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
