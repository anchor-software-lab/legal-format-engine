# legal-format-engine

Public repo. Base product for Anchor Labs LLC — the legal document
formatting engine that ships as a Microsoft Word plugin.

## Company Context

Anchor Labs LLC. This is the first and flagship product. The ML backend
lives in the private `anchor-software-lab/anchor-ml-engine` repo.

## What This Repo Contains

- Rules-based formatting engine (Rules > ML > Defaults hierarchy)
- ML integration layer that consumes format-only exports from the private ML engine
- Content consumer for structural patterns (argument outlines, citation patterns)
- No private document content ever enters this repo

## Key Files

- `src/legal_format_engine/ml_integration/format_consumer.py` — loads ML format specs
- `src/legal_format_engine/ml_integration/content_consumer.py` — loads structural specs
- `src/legal_format_engine/learned_formats/` — imported JSON specs (format only)

## Running

```bash
pip install -e ".[dev]"
pytest tests/
```
