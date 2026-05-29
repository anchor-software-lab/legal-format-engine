# legal-format-engine → Anchor Quality Gate

Public repo. Flagship product for Anchor Labs LLC. Originally a Word
formatting plugin; now being expanded into an **AI Quality Gate for
legal documents** — what an obsessive first-year associate with insane
attention to detail would do: ingest a docx, flag and correct
formatting, check citations, validate Bluebook form, verify good-law
status, learn firm preferences. Distributed as Word plugins (Office
Add-in + VSTO), a web app, and a Claude skill. SaaS-built with
customer-managed envelope encryption keys, LLM-agnostic via LiteLLM,
backed by a scraper of WI + federal authority.

## Company Context

Anchor Labs LLC. The ML backend lives in the private
`anchor-software-lab/anchor-ml-engine` repo and is consumed (format-only,
no document content) by `legal_format_engine`.

## Repo Layout

This is a monorepo (uv workspace for Python, pnpm for TypeScript,
dotnet for VSTO). Top level:

```
packages/                   Python packages
  legal_format_engine/      existing — formatting checker (Rules > ML > Defaults)
  legal_quality_gate/       NEW — orchestrator, Checker protocol, pipeline
  legal_docx/               docx/pdf parse, segment, annotated writer
  legal_citations/          Bluebook parser, normalizer, comparator
  legal_authority/          CourtListener/CAP client, good-law graph
  legal_authority_scraper/  WI + federal scraper service
  legal_llm_gateway/        LiteLLM wrapper, prompts, schemas, cost
  legal_style_memory/       firm/user style guides, correction history
  legal_api/                FastAPI SaaS surface, envelope crypto
  legal_cli/                `lqg` Typer CLI
  legal_skill_kit/          builds the distributable Claude skill
apps/
  office-addin/             React + TS + Office.js Word taskpane
  vsto-addin/               C# / .NET Framework 4.8 (Windows power users)
  web/                      Next.js 15 dashboard / admin / billing
schemas/                    OpenAPI + JSON schemas + versioned prompts
infra/                      Docker, Terraform, migrations, Helm
fixtures/                   sample docx + golden expected findings
skill/                      distributable Claude skill artifact
docs/                       ADRs, architecture
tools/                      dev scripts, codegen, LLM eval harness
```

Most packages are scaffolded for v0/v1/v2 work per the plan; see
`/root/.claude/plans/alright-i-want-to-serene-wozniak.md` for the
current rework plan and phasing.

## Architectural Principles

- **Rules > ML > Defaults** hierarchy (with confidence thresholds and
  provenance tracking) stays at the core. Every `Finding` carries a
  `provenance` field (`rule | ml | llm | hybrid`).
- **No raw document content** leaves the encryption boundary. Segments
  carry hashes + offsets; checkers retrieve text via
  `CheckContext.get_text(segment)` so the boundary is enforceable.
- **Deterministic before LLM** in the pipeline. Cheap fast findings
  surface before paying for LLM calls.
- **Stable rule_id taxonomy** (`FORMAT.FONT.SIZE`, `BB.SIGNAL.UNDERLINE`,
  `CITE.GHOST`, …). Never reuse an ID for different semantics.
- **schemas/ is source of truth** for cross-language contracts (Python,
  TS, C#).

## Key Files

Existing (reused):
- `packages/legal_format_engine/src/legal_format_engine/ml_integration/format_consumer.py`
  — `merge_with_rules`, `FormatSpec`, `load_format_spec`. The
  Rules > ML > Defaults logic and 0.3 ML confidence threshold are
  unchanged.
- `packages/legal_format_engine/src/legal_format_engine/ml_integration/content_consumer.py`
  — `LearnedSection`, `suggest_argument_outline`, `CitationPatterns`.

New (foundation):
- `packages/legal_quality_gate/src/legal_quality_gate/types.py` — domain
  model (`Document`, `Segment`, `Finding`, `Suggestion`, …).
- `packages/legal_quality_gate/src/legal_quality_gate/checker.py` —
  `Checker` protocol + `CheckContext`.
- `packages/legal_quality_gate/src/legal_quality_gate/pipeline.py` —
  orchestrator that runs checkers and produces a `QualityReport`.
- `packages/legal_format_engine/src/legal_format_engine/checkers/formatting_checker.py`
  — `formatting.spec_diff` checker that wraps `merge_with_rules` as a
  pipeline-compatible checker.

## Running

```bash
pip install pytest pydantic pyyaml
pytest                       # runs every package's tests
```

For a single package:

```bash
pytest packages/legal_quality_gate/tests
```

A `uv` workspace is configured in the root `pyproject.toml` for
production installs (`uv sync`).
