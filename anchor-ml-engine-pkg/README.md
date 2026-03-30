# Anchor ML Engine

A domain-agnostic ML engine for document format learning and style synthesis. Extracts formatting patterns from collections of documents and learns consensus styles using statistical methods (weighted median, IQR outlier rejection, categorical voting).

## Architecture

The engine has five layers:

1. **Normalizer** -- Canonicalizes fonts (50+ PostScript/CSS variants mapped to families), snaps measurements to standard increments, and produces format-agnostic `NormalizedDocument` objects.

2. **Feature Extractor** -- Converts normalized documents into weighted feature vectors. Features include typography, layout, headings, and section structure. PDF-derived values get lower confidence weights than DOCX values.

3. **Learner** -- Statistical pattern learning with IQR outlier rejection for numerical features and weighted voting for categorical features. Produces `LearnedFormat` objects with per-feature confidence scores.

4. **Synthesizer** -- Generates YAML-compatible rulesets from learned patterns and diffs against existing rulesets to produce recommendations.

5. **Pipeline** -- End-to-end orchestrator that coordinates ingestion, normalization, feature extraction, learning, and synthesis.

## Key Design Decisions

- **Rules always win**: Mandatory formatting rules override ML-learned patterns. The hierarchy is: Rules > ML Learned > Style Profiles > Defaults.
- **No neural networks**: Document formatting is deterministic. The ML uses weighted statistics, not deep learning.
- **Domain-agnostic core**: The normalizer, feature extractor, learner, and synthesizer work for any document domain. The firm database and attribution modules are legal-specific extensions.

## Installation

```bash
pip install anchor-ml-engine

# With optional connectors for DOCX/PDF processing:
pip install anchor-ml-engine[legal]

# For development:
pip install anchor-ml-engine[dev]
```

## Quick Start

```python
from anchor_ml_engine import MLPipeline, FormatLearner, extract_features

# End-to-end pipeline
pipeline = MLPipeline()
doc = pipeline.ingest("report.docx", category="quarterly_reports")
learned = pipeline.learn(category="quarterly_reports")
ruleset = pipeline.suggest_ruleset(category="quarterly_reports")

# Manual learning from feature vectors
learner = FormatLearner()
learner.add(extract_features(doc1))
learner.add(extract_features(doc2))
result = learner.learn()
print(result.font_family)  # LearnedValue with confidence
print(result.overall_confidence)
```

## Modules

| Module | Description |
|--------|-------------|
| `models` | All Pydantic models used across the pipeline |
| `normalizer` | Font canonicalization, measurement snapping, document normalization |
| `features` | Feature extraction from normalized documents |
| `learner` | Statistical pattern learning (weighted median, IQR, voting) |
| `synthesizer` | Ruleset generation and diffing |
| `pipeline` | End-to-end orchestrator |
| `attribution` | Auto-detect author/organization from documents |
| `firm_database` | 160+ law firms with fuzzy matching |
| `archive` | ZIP/RAR/PDF portfolio extraction |
| `style_profiles` | Per-author/organization formatting preferences |
| `rule_hierarchy` | Rules > ML > Style > Defaults enforcement |
| `pattern_store` | JSON storage for learned patterns |
| `connectors.docx` | DOCX format profile extraction |
| `connectors.pdf` | PDF format profile extraction |
| `connectors.gdocs` | Google Docs HTML export parsing |

## License

MIT
