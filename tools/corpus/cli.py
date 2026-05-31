"""`python -m tools.corpus.cli ...` command-line surface.

Five subcommands matching the pipeline:

  discover  fetch brief URLs from wicourts.gov
  download  fetch the PDFs to a local cache directory
  extract   eyecite-extract candidate cases from PDFs (or raw text)
  triage    interactive labeling loop with checkpoints
  merge     concatenate labeled JSONLs (skip duplicates)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from tools.corpus.extract import (
    extract_candidates_from_pdf,
    extract_candidates_from_text,
    write_candidates,
)
from tools.corpus.pdf import extract_text
from tools.corpus.state import TriageState, load_state, save_state
from tools.corpus.triage import TriageQuit, run_triage
from tools.corpus.wicourts import BriefRef, WICourtsClient

app = typer.Typer(
    name="corpus",
    help="Wisconsin brief corpus bootstrap",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def discover(
    out: Path = typer.Option(..., "--out", "-o", help="Write BriefRef JSON list here."),
    court: str = typer.Option("coa", "--court", help="coa | sc"),
    max_count: int = typer.Option(50, "--max", "-n"),
    cache_dir: Optional[Path] = typer.Option(
        Path("tools/corpus/.cache"), "--cache-dir"
    ),
) -> None:
    """Discover up to N brief PDF URLs from wicourts.gov."""
    console = Console()
    client = WICourtsClient(cache_dir=cache_dir)
    refs = asyncio.run(client.discover_briefs(court=court, max_count=max_count))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            [{"pdf_url": r.pdf_url, "docket": r.docket} for r in refs],
            indent=2,
        )
    )
    console.print(f"[green]Discovered {len(refs)} briefs[/] → {out}")


@app.command()
def download(
    refs_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    cache_dir: Path = typer.Option(
        Path("tools/corpus/.cache"), "--cache-dir"
    ),
) -> None:
    """Download all briefs in a discovery list to the cache directory."""
    console = Console()
    refs_raw = json.loads(refs_path.read_text())
    refs = [BriefRef(pdf_url=r["pdf_url"], docket=r.get("docket")) for r in refs_raw]
    client = WICourtsClient(cache_dir=cache_dir)

    async def _go() -> None:
        for ref in refs:
            try:
                await client.download_brief(ref)
                console.print(f"[green]✓[/] {ref.pdf_url}")
            except Exception as exc:  # noqa: BLE001
                console.print(f"[red]✗[/] {ref.pdf_url}: {exc}")

    asyncio.run(_go())


@app.command()
def extract(
    pdf_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    out: Path = typer.Option(..., "--out", "-o", help="Candidates JSONL output."),
    jurisdiction: str = typer.Option("WI", "--jurisdiction"),
    context_window: int = typer.Option(200, "--context-window"),
    text: bool = typer.Option(False, "--text", help="Input is plain text, not a PDF."),
    id_prefix: Optional[str] = typer.Option(None, "--id-prefix"),
) -> None:
    """Extract candidate citations from a single PDF (or text file) into a JSONL."""
    console = Console()
    source = str(pdf_path)
    if text:
        body = pdf_path.read_text()
        candidates = extract_candidates_from_text(
            body,
            brief_source=source,
            jurisdiction=jurisdiction,
            context_window=context_window,
            id_prefix=id_prefix,
        )
    else:
        pdf = extract_text(pdf_path.read_bytes())
        candidates = extract_candidates_from_pdf(
            pdf,
            brief_source=source,
            jurisdiction=jurisdiction,
            context_window=context_window,
            id_prefix=id_prefix,
        )
    write_candidates(candidates, out)
    console.print(
        f"[green]Extracted {len(candidates)} candidate citations[/] → {out}"
    )


@app.command()
def triage(
    candidates_path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True
    ),
    out: Path = typer.Option(..., "--out", "-o", help="Labeled JSONL output (appended)."),
    session_dir: Path = typer.Option(
        ..., "--session-dir",
        help="Directory to persist checkpoint state in; resumed if it exists.",
    ),
) -> None:
    """Interactive triage loop with checkpoints."""
    console = Console()
    state = load_state(session_dir)
    if state is None:
        state = TriageState(
            session_id=str(uuid.uuid4()),
            candidates_path=str(candidates_path),
            output_path=str(out),
        )
        save_state(session_dir, state)
        console.print(f"[blue]Starting new triage session[/] in {session_dir}")
    else:
        console.print(
            f"[blue]Resuming session[/] {state.session_id} at index "
            f"{state.next_index}"
        )
    try:
        run_triage(
            candidates_path=candidates_path,
            output_path=out,
            session_dir=session_dir,
            state=state,
            console=console,
        )
    except TriageQuit:
        pass
    console.print("[green]Done.[/]")


@app.command()
def merge(
    inputs: list[Path] = typer.Argument(..., exists=True, dir_okay=False),
    out: Path = typer.Option(..., "--out", "-o"),
) -> None:
    """Merge labeled JSONLs, dropping duplicate ids (keeping the first)."""
    console = Console()
    seen: set[str] = set()
    n = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        for path in inputs:
            with open(path) as src:
                for line in src:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    rec = json.loads(line)
                    if rec.get("id") in seen:
                        continue
                    seen.add(rec.get("id", ""))
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n += 1
    console.print(f"[green]Merged {n} unique cases[/] → {out}")


if __name__ == "__main__":
    app()
