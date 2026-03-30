"""Legal Format Engine: rules-based legal document formatting.

This package provides:
- rules: Mandatory formatting rules for legal documents by jurisdiction
- ml_integration: Consumes ML-learned patterns (format + structure, no verbatim content)
  - format_consumer: Typography, layout, heading patterns
  - content_consumer: Argument structure, citation patterns, reasoning models
- learned_formats: Storage for imported format and structure specs
- formatter: Applies resolved formatting to documents
"""

from legal_format_engine.ml_integration.format_consumer import (
    FormatSpec,
    load_format_spec,
    merge_with_rules,
)

from legal_format_engine.ml_integration.content_consumer import (
    DocumentStructureSpec,
    load_structure_spec,
    suggest_argument_outline,
)

__all__ = [
    # Format integration
    "FormatSpec",
    "load_format_spec",
    "merge_with_rules",
    # Content/structure integration
    "DocumentStructureSpec",
    "load_structure_spec",
    "suggest_argument_outline",
]
