# legal-format-engine

Rules-based legal document formatting engine with ML-learned pattern support.

## Architecture

The legal format engine applies formatting to legal documents using a strict hierarchy:

1. **Mandatory Rules** — Court-specific formatting requirements that cannot be overridden
2. **ML-Learned Patterns** — Formatting patterns learned from real documents via `anchor-ml-engine` (private)
3. **Defaults** — Sensible fallback values

## ML Integration

This engine consumes **format-only** data from the private `anchor-ml-engine` repository.
The ML engine processes real legal documents to learn formatting patterns (typography,
margins, heading styles, section ordering) but **never exposes document content**.

The data flow is one-directional:

```
anchor-ml-engine (PRIVATE)          legal-format-engine (PUBLIC)
├── training_data/                  ├── src/legal_format_engine/
│   └── cases/...                   │   ├── ml_integration/
│       (sensitive documents)       │   │   └── format_consumer.py
│                                   │   └── learned_formats/
├── src/anchor_ml_engine/           │       └── *.json (format-only specs)
│   ├── pipeline.py                 │
│   └── format_export.py ──JSON──>  └── Only formatting metadata crosses
│       (strips all content)            this boundary. Never content.
```

## Installation

```bash
pip install legal-format-engine

# With ML engine support (requires access to private repo):
pip install legal-format-engine[ml]
```

## Quick Start

```python
from legal_format_engine import load_format_spec, merge_with_rules

# Load ML-learned formatting patterns
spec = load_format_spec("learned_formats/appellate_wisconsin_coa.json")

# Define mandatory court rules
rules = {
    "page_format": {
        "font_size_pt": 13.0,       # WI COA requirement
        "line_spacing": 2.0,         # Double-spaced
        "margin_top_inches": 1.0,
    }
}

# Merge: Rules > ML-Learned > Defaults
resolved = merge_with_rules(rules, ml_spec=spec)
print(resolved["font_name"])          # From ML or default
print(resolved["_provenance"])        # Shows where each value came from
```

## License

MIT
