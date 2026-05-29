# Legal Format Engine → Anchor Quality Gate

**Anchor Labs LLC** — formerly a rules-based Word formatting engine,
now being expanded into a complete **AI Quality Gate for legal
documents**: ingest a docx, flag and correct formatting, check
citations, validate Bluebook form, verify good-law status, learn firm
preferences. Distributed as Word plugins (Office Add-in + VSTO), a web
app, and a Claude skill. SaaS-built with customer-managed envelope
encryption, LLM-agnostic via LiteLLM, backed by a scraper of WI +
federal authority.

The rework is in progress. The structural foundation (monorepo,
Checker protocol, pipeline, formatting checker wrapping the existing
engine) is in place. See `CLAUDE.md` for the current architecture.

## Product Roadmap

| Phase | Status | Scope |
|-------|--------|-------|
| Format engine library | Shipped | Rules > ML > Defaults merge with provenance |
| **v0 — Engine MVP** | In progress | docx parse, Bluebook deterministic, CLI |
| v1 — Cloud + Office Add-in | Planned | FastAPI + LLM gateway + plugin + skill |
| v2 — Scraper + Web + VSTO | Planned | WI/federal authority + dashboard + VSTO |

The private `anchor-ml-engine` repo continues to learn formatting,
citation, and reasoning patterns from real legal documents and exports
format-only JSON specs that this engine consumes.

## How It Works

The formatting engine applies a strict hierarchy:

1. **Mandatory Rules** — Court-specific formatting requirements (always win)
2. **ML-Learned Patterns** — Formatting patterns learned from real briefs
   via the private ML engine
3. **Defaults** — Sensible fallback values

```python
from legal_format_engine import load_format_spec, merge_with_rules

# Load ML-learned patterns (exported from private ML engine)
spec = load_format_spec("learned_formats/appellate_wisconsin_coa.json")

# Court rules (mandatory)
rules = {"page_format": {"font_size_pt": 13.0, "line_spacing": 2.0}}

# Merge: Rules > ML > Defaults
resolved = merge_with_rules(rules, ml_spec=spec)
```

## ML Integration

This engine consumes **format-only** data from the private ML engine.
No private document content ever enters this public repository.

```
anchor-ml-engine (PRIVATE)          legal-format-engine (PUBLIC)
├── engines/                        ├── packages/legal_format_engine/
│   └── FormatEngine ──►            │   └── src/legal_format_engine/
│       export_learned_format()     │       ├── ml_integration/
│           │                       │       │   ├── format_consumer.py
│           └── JSON ──────────►    │       │   └── content_consumer.py
│       (formatting patterns only)  │       └── learned_formats/*.json
```

## Repo Layout

This is a monorepo. Top-level:

```
packages/                   Python packages (uv workspace)
  legal_format_engine/      Formatting checker (Rules > ML > Defaults)
  legal_quality_gate/       Orchestrator + Checker protocol + pipeline
  legal_docx/               docx parse, segment, annotated writer
  legal_citations/          Bluebook parser/normalizer
  legal_authority/          CourtListener/CAP client, good-law graph
  legal_authority_scraper/  WI + federal scraper service
  legal_llm_gateway/        LiteLLM wrapper, prompts, cost
  legal_style_memory/       firm/user style guides, correction history
  legal_api/                FastAPI SaaS surface
  legal_cli/                `lqg` CLI
  legal_skill_kit/          builds the distributable Claude skill
apps/                       office-addin, vsto-addin, web
schemas/                    OpenAPI + JSON schemas + prompts (source of truth)
infra/                      Docker, Terraform, migrations
fixtures/                   sample docx + golden findings + policies
```

## Installation

The format engine library still installs standalone:

```bash
pip install ./packages/legal_format_engine
```

For workspace development:

```bash
uv sync                       # installs all packages in dev mode
pytest                        # runs every package's tests
```

## License

MIT

---

*Anchor Labs LLC*
