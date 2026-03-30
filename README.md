# legal-format-engine

Rules-based legal document formatting engine.

## Overview

This engine stores and applies jurisdiction-specific formatting rules for legal
documents. Rules are extracted from real formatting sessions via the
[anchor-ml-engine](https://github.com/anchor-software-lab/anchor-ml-engine)'s
session learning pipeline.

## Structure

```
legal-format-engine/
├── jurisdictions/           # Jurisdiction-specific formatting rules (YAML)
│   └── wisconsin/
│       └── circuit_court.yaml
├── src/
│   └── legal_format_engine/ # Python package (future)
└── Dunnington_Session_PostMortem.md  # Source session data
```

## How Rules Are Learned

1. A formatting session produces a **post-mortem markdown file** documenting
   iterations, errors, and extracted formatting rules.
2. The `anchor-ml-engine` parses the post-mortem via `SessionParser` and stores
   it as a `SessionRecord`.
3. Formatting rules are extracted and stored in a `JurisdictionProfile`.
4. The TensorFlow `ErrorPredictor` model trains on iteration data to predict
   which errors are likely given a document's context (jurisdiction, court level,
   document type, generation method).
5. The `CorrectionRecommender` model learns from before/after correction pairs
   to suggest fixes.

## Jurisdiction Rules

Rules are stored as YAML files under `jurisdictions/<state>/<court_level>.yaml`.
Each file contains:

- **Caption formatting** (table structure, fonts, borders)
- **Body text rules** (font, spacing, alignment, indentation)
- **Signature block rules** (line characters, lengths, tab stops)
- **eFiling requirements** (margins, file format, signature handling)
- **Voice conventions** (court vs. counsel language)
- **Technical rules** (XML editing patterns, common pitfalls)

## Usage with anchor-ml-engine

```python
from anchor_ml_engine import MLPipeline

pipeline = MLPipeline()

# Ingest a session post-mortem
result = pipeline.ingest_session("Dunnington_Session_PostMortem.md")

# View the extracted jurisdiction profile
profile = pipeline.get_jurisdiction_profile("wisconsin", "circuit")

# Train the error predictor from session data
training_result = pipeline.train_error_predictor()

# List all learned sessions
sessions = pipeline.list_sessions()
```
