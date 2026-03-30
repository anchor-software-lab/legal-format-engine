"""CLI entry point for legal-format command."""

from __future__ import annotations
from pathlib import Path
from typing import Optional

import click

from legal_format_engine.models.document import (
    Attorney,
    CaseMetadata,
    DocumentMetadata,
    Party,
    PartyRole,
)
from legal_format_engine.pipeline import (
    format_and_render_docx,
    format_and_render_markdown,
    validate_document,
)
from legal_format_engine.engines.caption_engine import generate_caption
from legal_format_engine.engines.citation_engine import check_citations
from legal_format_engine.rules.base import load_ruleset, list_rulesets


@click.group()
def cli():
    """Legal Format Engine - Rules-based legal document formatting."""
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--jurisdiction", "-j", default="wisconsin", help="Jurisdiction")
@click.option("--document-type", "-d", default="appellate_brief", help="Document type")
@click.option("--case-number", help="Case number")
@click.option("--case-name", help="Case name")
@click.option("--format", "output_format", default="docx", type=click.Choice(["docx", "markdown"]))
def format(input_file, output, jurisdiction, document_type, case_number, case_name, output_format):
    """Format a legal document."""
    text = Path(input_file).read_text()

    doc_meta = DocumentMetadata(
        jurisdiction=jurisdiction,
        document_type=document_type,
    )

    case_meta = None
    if case_number or case_name:
        case_meta = CaseMetadata(
            case_name=case_name or "",
            case_number=case_number or "",
        )

    if output_format == "docx":
        output = output or "output.docx"
        data = format_and_render_docx(text, case_meta, doc_meta, output_path=output)
        click.echo(f"Written to {output} ({len(data)} bytes)")
    else:
        md = format_and_render_markdown(text, case_meta, doc_meta)
        if output:
            Path(output).write_text(md)
            click.echo(f"Written to {output}")
        else:
            click.echo(md)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--jurisdiction", "-j", default="wisconsin")
@click.option("--document-type", "-d", default="appellate_brief")
def validate(input_file, jurisdiction, document_type):
    """Validate document structure."""
    text = Path(input_file).read_text()
    doc_meta = DocumentMetadata(jurisdiction=jurisdiction, document_type=document_type)
    issues = validate_document(text, doc_meta)

    if not issues:
        click.echo("✓ No issues found")
    else:
        for issue in issues:
            icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(issue.severity, "?")
            click.echo(f"  {icon} [{issue.code}] {issue.message}")
        click.echo(f"\n{len(issues)} issue(s) found")


@cli.command()
@click.option("--case-name", required=True)
@click.option("--case-number", required=True)
@click.option("--jurisdiction", "-j", default="wisconsin")
@click.option("--document-type", "-d", default="appellate_brief")
@click.option("--document-title", default="Brief of Defendant-Appellant")
@click.option("--district", default=None)
def caption(case_name, case_number, jurisdiction, document_type, document_title, district):
    """Generate a caption block."""
    ruleset = load_ruleset(jurisdiction, document_type)
    case_meta = CaseMetadata(
        case_name=case_name,
        case_number=case_number,
        district=district,
    )
    cap = generate_caption(case_meta, document_title, ruleset)
    for line in cap.lines:
        click.echo(line.text)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
def citations(input_file):
    """Check citation consistency."""
    text = Path(input_file).read_text()
    report = check_citations(text)

    click.echo(f"Found {report.stats.get('total', 0)} citations")
    for key in ("case", "statute", "id", "short"):
        count = report.stats.get(key, 0)
        if count:
            click.echo(f"  {key}: {count}")

    if report.issues:
        click.echo(f"\n{len(report.issues)} issue(s):")
        for issue in report.issues:
            icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(issue.severity, "?")
            click.echo(f"  {icon} [{issue.code}] {issue.message}")
    else:
        click.echo("\n✓ No citation issues found")


@cli.command(name="list-rulesets")
def list_rulesets_cmd():
    """List available rulesets."""
    for rs in list_rulesets():
        click.echo(f"  {rs['jurisdiction']}/{rs['document_type']}")


@cli.command()
@click.argument("directory", type=click.Path(exists=True))
def analyze(directory):
    """Analyze briefs in a directory for formatting patterns."""
    from legal_format_engine.tools.analyze_brief import analyze_directory

    results = analyze_directory(directory)
    click.echo(f"Analyzed {len(results)} documents")
    for r in results:
        click.echo(f"\n  {r['file_name']}:")
        if r.get("dominant_font"):
            click.echo(f"    Font: {r['dominant_font']}")
        if r.get("margins"):
            m = r["margins"]
            click.echo(f"    Margins: T={m.get('top', '?')} B={m.get('bottom', '?')} "
                       f"L={m.get('left', '?')} R={m.get('right', '?')}")
        if r.get("headings"):
            click.echo(f"    Headings: {len(r['headings'])} detected")


if __name__ == "__main__":
    cli()
