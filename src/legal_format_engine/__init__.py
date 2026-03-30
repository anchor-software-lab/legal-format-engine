"""Legal Format Engine: rules-based legal document formatting.

This package provides:
- rules: Mandatory formatting rules for legal documents by jurisdiction
- ml_integration: Consumes ML-learned formatting patterns (format only, no content)
- learned_formats: Storage for imported format specs from the ML engine
- formatter: Applies resolved formatting to documents
"""

from legal_format_engine.ml_integration.format_consumer import (
    FormatSpec,
    load_format_spec,
    merge_with_rules,
)

__all__ = [
    "FormatSpec",
    "load_format_spec",
    "merge_with_rules",
]
