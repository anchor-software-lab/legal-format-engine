"""Wisconsin brief corpus bootstrap.

Walks wicourts.gov for publicly filed appellate briefs, extracts
citations with eyecite, surfaces them for fast human triage, and
emits labeled JSONL ready for `tools/eval/datasets/`. Grows the
hand-labeled corpus from the 15-case smoke seed up to whatever
volume the user has triage stamina for.

Pipeline:

    discover  →  download  →  extract  →  triage  →  merge
    URL list     PDFs         candidate     human-     ready for
                 cached       cases JSONL   labeled    eval
                              with context  JSONL

Each step is checkpointable; running again resumes where the previous
session left off. Tests use httpx.MockTransport against fixture HTML
+ checked-in fixture PDFs so they stay offline.

Layout:

    tools/corpus/
    ├── wicourts.py      WI courts scraper client + URL discovery
    ├── pdf.py           pdfplumber wrapper, plus context-window helper
    ├── extract.py       eyecite → candidate EvalCases with context
    ├── triage.py        interactive labeling loop
    ├── state.py         checkpoint persistence
    ├── cli.py           `python -m tools.corpus.cli ...`
    └── tests/

What this tool does NOT do:
- Bulk-download all of wicourts.gov. Discovery accepts a max-count
  and respects rate limits.
- Strip metadata from briefs. Caller is responsible for the privacy
  posture of any downloaded brief. The triage step never persists
  full brief text, only the chosen citation excerpts.
"""
