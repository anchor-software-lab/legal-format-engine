"""Command-line interface for the legal format engine."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from legal_format_engine.engines.pipeline import (
    format_and_render_docx,
    format_and_render_markdown,
    format_document,
)
from legal_format_engine.models.metadata import DocumentMetadata
from legal_format_engine.rules.loader import load_ruleset


@click.group()
@click.version_option()
def main() -> None:
    """Legal Format Engine - Rules-based legal document formatting."""


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), required=True, help="Output file path.")
@click.option("--metadata", "-m", type=click.Path(exists=True), required=True,
              help="JSON file with case/document metadata.")
@click.option("--jurisdiction", default="wisconsin", help="Jurisdiction (default: wisconsin).")
@click.option("--court-level", default="appellate", help="Court level (default: appellate).")
@click.option("--doc-type", default="brief", help="Document type (default: brief).")
@click.option("--variant", default=None, help="Ruleset variant override.")
@click.option("--format", "output_format", type=click.Choice(["docx", "markdown"]),
              default="docx", help="Output format.")
@click.option("--word-count", type=int, default=None, help="Word count for compliance cert.")
def format(
    input_file: str,
    output: str,
    metadata: str,
    jurisdiction: str,
    court_level: str,
    doc_type: str,
    variant: str | None,
    output_format: str,
    word_count: int | None,
) -> None:
    """Format a legal document according to jurisdiction rules.

    Reads INPUT_FILE (plain text or .docx), applies formatting rules,
    and writes the formatted output to --output.
    """
    # Load metadata
    meta_path = Path(metadata)
    meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
    doc_metadata = DocumentMetadata.model_validate(meta_data)

    # Load ruleset
    try:
        ruleset = load_ruleset(jurisdiction, court_level, doc_type, variant=variant)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Read input - support plain text, DOCX, and PDF
    input_path = Path(input_file)
    if input_path.suffix == ".docx":
        from legal_format_engine.parsers.docx_parser import parse_docx
        doc = parse_docx(input_path)
        text = doc.raw_text or ""
    elif input_path.suffix == ".pdf":
        from legal_format_engine.parsers.pdf_parser import parse_pdf
        doc = parse_pdf(input_path)
        text = doc.raw_text or ""
    else:
        text = input_path.read_text(encoding="utf-8")

    # Format and render
    if output_format == "docx":
        doc, path = format_and_render_docx(
            text, doc_metadata, ruleset, output, word_count=word_count
        )
        click.echo(f"DOCX written to: {path}")
    else:
        doc, md = format_and_render_markdown(
            text, doc_metadata, ruleset, word_count=word_count
        )
        Path(output).write_text(md, encoding="utf-8")
        click.echo(f"Markdown written to: {output}")

    # Report issues
    if doc.issues:
        click.echo(f"\n{len(doc.issues)} issue(s) found:")
        for issue in doc.issues:
            icon = {"error": "x", "warning": "!", "info": "i"}[issue.severity]
            click.echo(f"  [{icon}] {issue.code}: {issue.message}")


@main.command()
@click.option("--metadata", "-m", type=click.Path(exists=True), required=True,
              help="JSON file with case/document metadata.")
@click.option("--jurisdiction", default="wisconsin")
@click.option("--court-level", default="appellate")
@click.option("--doc-type", default="brief")
@click.option("--variant", default=None, help="Ruleset variant override.")
def caption(metadata: str, jurisdiction: str, court_level: str, doc_type: str,
            variant: str | None) -> None:
    """Generate just a caption block and print it."""
    from legal_format_engine.engines.caption_engine import generate_caption

    meta_data = json.loads(Path(metadata).read_text(encoding="utf-8"))
    doc_metadata = DocumentMetadata.model_validate(meta_data)

    ruleset = load_ruleset(jurisdiction, court_level, doc_type, variant=variant)
    cap = generate_caption(doc_metadata, ruleset.caption_rule)

    for line in cap.lines:
        click.echo(line.text)


@main.command()
@click.option("--metadata", "-m", type=click.Path(exists=True), required=True,
              help="JSON file with case/document metadata.")
@click.option("--input-file", "-i", type=click.Path(exists=True), required=True,
              help="Plain text or DOCX file to validate.")
@click.option("--jurisdiction", default="wisconsin")
@click.option("--court-level", default="appellate")
@click.option("--doc-type", default="brief")
@click.option("--variant", default=None, help="Ruleset variant override.")
def validate(
    metadata: str, input_file: str, jurisdiction: str, court_level: str,
    doc_type: str, variant: str | None,
) -> None:
    """Validate document structure against jurisdiction rules."""
    meta_data = json.loads(Path(metadata).read_text(encoding="utf-8"))
    doc_metadata = DocumentMetadata.model_validate(meta_data)

    ruleset = load_ruleset(jurisdiction, court_level, doc_type, variant=variant)

    input_path = Path(input_file)
    if input_path.suffix == ".docx":
        from legal_format_engine.parsers.docx_parser import parse_docx
        parsed = parse_docx(input_path)
        text = parsed.raw_text or ""
    elif input_path.suffix == ".pdf":
        from legal_format_engine.parsers.pdf_parser import parse_pdf
        parsed = parse_pdf(input_path)
        text = parsed.raw_text or ""
    else:
        text = input_path.read_text(encoding="utf-8")

    doc = format_document(text, doc_metadata, ruleset, insert_missing=False)

    if not doc.issues:
        click.echo("Document structure is valid.")
    else:
        click.echo(f"{len(doc.issues)} issue(s) found:")
        for issue in doc.issues:
            icon = {"error": "x", "warning": "!", "info": "i"}[issue.severity]
            click.echo(f"  [{icon}] {issue.code}: {issue.message}")
        sys.exit(1 if any(i.severity == "error" for i in doc.issues) else 0)


@main.command()
@click.argument("path", type=click.Path(exists=True))
def analyze(path: str) -> None:
    """Analyze a DOCX brief (or directory of briefs) to extract formatting patterns.

    Use this to derive rules from reference briefs.
    """
    from legal_format_engine.tools.analyze_brief import analyze_brief, analyze_directory

    target = Path(path)
    if target.is_dir():
        analyze_directory(target)
    elif target.suffix == ".docx":
        analyze_brief(target)
    elif target.suffix == ".pdf":
        from legal_format_engine.parsers.pdf_parser import extract_pdf_format_profile, parse_pdf
        profile = extract_pdf_format_profile(target)
        doc = parse_pdf(target)
        click.echo(f"\n{'='*70}")
        click.echo(f"PDF Analysis: {target.name}")
        click.echo(f"{'='*70}")
        page = profile.get("page", {})
        click.echo(f"  Page: {page.get('width_inches')}\" x {page.get('height_inches')}\"")
        margins = profile.get("margins_estimated", {})
        if margins:
            click.echo(f"  Margins (est): L={margins.get('left_inches')}\" "
                        f"R={margins.get('right_inches')}\" "
                        f"T={margins.get('top_inches')}\" "
                        f"B={margins.get('bottom_inches')}\"")
        fonts = profile.get("fonts", {})
        click.echo(f"  Font: {fonts.get('dominant', 'Unknown')}")
        sizes = profile.get("font_sizes", {})
        click.echo(f"  Size: {sizes.get('dominant_pt', '?')}pt")
        click.echo(f"\n  Sections ({len(doc.sections)}):")
        for s in doc.sections:
            content_len = sum(len(b.text) for b in s.content)
            click.echo(f"    [{s.heading_level.name}] \"{s.heading_text}\" ({content_len} chars)")
    else:
        click.echo(f"Error: {target} is not a .docx, .pdf, or directory", err=True)
        sys.exit(1)


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
def citations(input_file: str) -> None:
    """Check citation consistency in a document.

    Detects inconsistent case names, Id. usage, signals, and spacing.
    """
    from legal_format_engine.engines.citation_engine import check_citation_consistency

    input_path = Path(input_file)
    if input_path.suffix == ".docx":
        from legal_format_engine.parsers.docx_parser import parse_docx
        doc = parse_docx(input_path)
        text = doc.raw_text or ""
    elif input_path.suffix == ".pdf":
        from legal_format_engine.parsers.pdf_parser import parse_pdf
        doc = parse_pdf(input_path)
        text = doc.raw_text or ""
    else:
        text = input_path.read_text(encoding="utf-8")

    report = check_citation_consistency(text)

    click.echo(f"Found {len(report.citations)} citation(s)")
    click.echo(f"  Cases: {sum(1 for c in report.citations if c.citation_type.value == 'case')}")
    click.echo(f"  Short cites: {sum(1 for c in report.citations if c.citation_type.value == 'short_cite')}")
    click.echo(f"  Id.: {sum(1 for c in report.citations if c.citation_type.value == 'id')}")
    click.echo(f"  Statutes: {len(report.statute_citations)}")

    if report.issues:
        click.echo(f"\n{len(report.issues)} issue(s):")
        for issue in report.issues:
            icon = {"error": "x", "warning": "!", "info": "i"}[issue.severity.value]
            click.echo(f"  [{icon}] {issue.code}: {issue.message}")
            if issue.suggestion:
                click.echo(f"      Suggestion: {issue.suggestion}")
    else:
        click.echo("\nNo citation consistency issues found.")


if __name__ == "__main__":
    main()
