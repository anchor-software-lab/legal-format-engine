# Wisconsin brief corpus bootstrap

Tooling for growing the LLM eval corpus from the 15-case smoke seed up
to 200+ hand-labeled real-world citations. Walks publicly filed
appellate briefs from `wicourts.gov`, extracts citations with eyecite,
surfaces them in a fast triage loop, and emits labeled JSONL ready for
`tools/eval/datasets/`.

## Workflow

```
discover  →  download  →  extract  →  triage  →  (merge)
URL list     PDFs         candidate     human-     ready for
             cached       cases JSONL   labeled    eval
                          with context  JSONL
```

Every step is checkpointable and resumable.

## Quickstart

```bash
# 1. Discover up to 25 recent briefs from the Court of Appeals.
make corpus-discover CORPUS_COURT=coa CORPUS_MAX=25

# 2. Download all of them into the local cache.
make corpus-download

# 3. Extract candidate citations from one brief at a time.
make corpus-extract CORPUS_PDF=tools/corpus/.cache/<digest>.pdf

# 4. Triage the candidates with checkpoints.
make corpus-triage
#    Each candidate shows:
#      - the citation as it appears in the brief
#      - 1-2 sentences of context
#      - a candidate canonical form derived from eyecite
#    Actions:
#      a / accept       keep the candidate as the gold label
#      e / edit         type a corrected canonical (and field overrides)
#      r / reject       drop it (eyecite confused, OCR ate it, etc.)
#      s / skip         decide later
#      q / quit         save state and stop; resume by re-running
```

State files in `tools/corpus/.session/` (gitignored) preserve progress
across sessions. Labeled cases append to
`tools/eval/datasets/bluebook.normalize_case/wi_corpus.jsonl`.

## Without the scraper

If you'd rather not hit the WI courts site directly (or it's slow that
day), pass any PDF or text file:

```bash
make corpus-extract       CORPUS_PDF=/path/to/your.pdf
make corpus-extract-text  CORPUS_TEXT=/path/to/your.txt
make corpus-triage
```

## Throughput

Empirically ~30 seconds per candidate during triage (read context,
hit `a` or type an edit). 200 cases ≈ 100 minutes of human time.

Each citation in a brief becomes ~1 candidate; parallel cites
("2010 WI 137, 330 Wis. 2d 389, 793 N.W.2d 860") are auto-deduped to
the lead cite by reusing `legal_citations.parser.is_parallel_continuation`,
so eight cites in a brief produce roughly four-to-six candidates after
dedupe. A typical 30-page appellate brief yields 30-60 candidates.

## Privacy + politeness

- The scraper sets a real `User-Agent` (`AnchorQualityGateBot/0.1`)
  with a contact address.
- Rate-limited to one HTTP call every 2s by default; tune via
  `WICourtsClient(min_delay_seconds=...)`.
- Discovery is read-only against public search pages. No
  authentication, no posting, no enumeration of sealed filings.
- Brief PDFs are public records under Wis. Stat. § 19.31. The triage
  step persists only citation excerpts (the candidate's `input.raw`
  and ~200 chars of `context`), never the full brief text.
- The cache directory (`tools/corpus/.cache/`) is gitignored. Don't
  commit downloaded briefs.

## Outputs

- `tools/corpus/.cache/discovered.json` — list of `{pdf_url, docket}`.
- `tools/corpus/.cache/<sha256>.pdf` — cached PDFs.
- `tools/corpus/.cache/candidates.jsonl` — extractor output.
- `tools/eval/datasets/bluebook.normalize_case/wi_corpus.jsonl` —
  labeled cases ready to feed into `tools/eval/cli.py run`.

Use `make corpus-merge INPUTS="a.jsonl b.jsonl" OUT=merged.jsonl` to
combine labeled outputs from multiple triage sessions; duplicates by
case id are skipped (first occurrence wins).
