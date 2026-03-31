# Legal Format Engine

**Anchor Labs LLC** — Rules-based legal document formatting engine.

This is the base product in the Anchor Labs portfolio. It ships as a
Microsoft Word plugin that formats legal documents according to
court-specific rules, supplemented by ML-learned patterns from real briefs.

## Product Roadmap

| Product | Status | Description |
|---------|--------|-------------|
| **Legal Format Engine** | Shipping | Word plugin for document formatting |
| Citation Checker | Planned | Bluebook/court-rule citation validation, added to the Word plugin |
| AI Legal Research | Planned | Midpage-style AI-powered legal research tool |

All products are backed by the private `anchor-ml-engine` repository,
which learns formatting, citation, and reasoning patterns from real
legal documents.

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
├── engines/                        ├── src/legal_format_engine/
│   └── FormatEngine ──►            │   ├── ml_integration/
│       export_learned_format()     │   │   ├── format_consumer.py
│           │                       │   │   └── content_consumer.py
│           └── JSON ──────────►    │   └── learned_formats/
│       (formatting patterns only)  │       └── *.json
```

## Package Layout

```
src/legal_format_engine/
├── ml_integration/
│   ├── format_consumer.py      Loads format specs, merges with rules
│   └── content_consumer.py     Loads structural specs (argument outlines)
├── learned_formats/             Imported format specs (JSON, no content)
└── __init__.py
```

## Installation

```bash
pip install legal-format-engine

# With ML engine (requires private repo access)
pip install legal-format-engine[ml]
```

## License

MIT

---

*Anchor Labs LLC*
